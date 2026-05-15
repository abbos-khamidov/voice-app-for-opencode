using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace VoiceReader.Windows;

public sealed class MainForm : Form
{
    private static readonly Regex SymbolsToSkip = new(@"[\-*—–•_~`#=<>|/\\\[\]{}]+", RegexOptions.Compiled);
    private static readonly Regex ExtraSpaces = new(@"\s+", RegexOptions.Compiled);
    private static readonly Regex SentenceParts = new(@"[^.!?;:]+[.!?;:]?|[^.!?;:]+$", RegexOptions.Compiled);

    private const int MaxChunkChars = 260;

    private readonly Dictionary<string, string> voices = new()
    {
        ["Ava Multilingual Natural"] = "en-US-AvaMultilingualNeural",
        ["Andrew Multilingual Natural"] = "en-US-AndrewMultilingualNeural",
        ["Emma Multilingual Natural"] = "en-US-EmmaMultilingualNeural",
        ["Brian Multilingual Natural"] = "en-US-BrianMultilingualNeural",
        ["Jenny (US English)"] = "en-US-JennyNeural",
        ["Guy (US English)"] = "en-US-GuyNeural",
        ["Svetlana (Russian)"] = "ru-RU-SvetlanaNeural",
        ["Dmitry (Russian)"] = "ru-RU-DmitryNeural",
    };

    private readonly Dictionary<string, (string Pitch, string Volume)> tones = new()
    {
        ["Natural"] = ("+0Hz", "+0%"),
        ["Lively"] = ("+8Hz", "+8%"),
        ["Confident"] = ("-2Hz", "+10%"),
        ["Soft"] = ("+4Hz", "-8%"),
    };

    private readonly TextBox textBox = new();
    private readonly ComboBox voiceBox = new();
    private readonly NumericUpDown speedBox = new();
    private readonly ComboBox toneBox = new();
    private readonly Button playButton = new();
    private readonly Button stopButton = new();
    private readonly Label statusLabel = new();
    private readonly System.Windows.Forms.Timer playbackTimer = new();
    private readonly Queue<string> playbackQueue = new();

    private CancellationTokenSource? cancellation;
    private dynamic? player;
    private bool generationFinished;
    private int bufferedChunks;

    private string AppDirectory => AppContext.BaseDirectory;
    private string OutputPath => Path.Combine(AppDirectory, "speech.mp3");
    private string TempOutputPath => Path.Combine(AppDirectory, "speech.tmp.mp3");
    private string ChunkDirectory => Path.Combine(AppDirectory, "tts_chunks");

    public MainForm()
    {
        Text = "Text Reader";
        Width = 900;
        Height = 620;
        MinimumSize = new System.Drawing.Size(760, 420);

        textBox.Multiline = true;
        textBox.ScrollBars = ScrollBars.Vertical;
        textBox.Dock = DockStyle.Fill;
        textBox.Font = new System.Drawing.Font("Segoe UI", 12);

        voiceBox.DropDownStyle = ComboBoxStyle.DropDownList;
        voiceBox.Items.AddRange(voices.Keys.Cast<object>().ToArray());
        voiceBox.SelectedIndex = 0;

        speedBox.Minimum = 50;
        speedBox.Maximum = 200;
        speedBox.Increment = 5;
        speedBox.Value = 100;
        speedBox.Width = 70;
        speedBox.ValueChanged += (_, _) =>
        {
            if (player is not null)
            {
                player.settings.rate = CurrentSpeed;
            }
            if (cancellation is not null)
            {
                SetStatus($"Speed changed to {CurrentSpeed:0.00}x");
            }
        };

        toneBox.DropDownStyle = ComboBoxStyle.DropDownList;
        toneBox.Items.AddRange(tones.Keys.Cast<object>().ToArray());
        toneBox.SelectedIndex = 0;

        playButton.Text = "Play";
        playButton.Click += async (_, _) => await PlayAsync();

        stopButton.Text = "Stop";
        stopButton.Click += (_, _) => Stop();

        statusLabel.Text = "Status: Ready";
        statusLabel.AutoSize = true;
        statusLabel.Padding = new Padding(6, 8, 0, 0);

        var controls = new FlowLayoutPanel
        {
            Dock = DockStyle.Bottom,
            Height = 48,
            FlowDirection = FlowDirection.LeftToRight,
            Padding = new Padding(8),
        };

        controls.Controls.Add(new Label { Text = "Voice", AutoSize = true, Padding = new Padding(0, 6, 0, 0) });
        controls.Controls.Add(voiceBox);
        controls.Controls.Add(new Label { Text = "Speed", AutoSize = true, Padding = new Padding(12, 6, 0, 0) });
        controls.Controls.Add(speedBox);
        controls.Controls.Add(new Label { Text = "Tone", AutoSize = true, Padding = new Padding(12, 6, 0, 0) });
        controls.Controls.Add(toneBox);
        controls.Controls.Add(playButton);
        controls.Controls.Add(stopButton);

        var bottom = new Panel { Dock = DockStyle.Bottom, Height = 82 };
        bottom.Controls.Add(statusLabel);
        bottom.Controls.Add(controls);

        Controls.Add(textBox);
        Controls.Add(bottom);

        playbackTimer.Interval = 80;
        playbackTimer.Tick += (_, _) => PlayNextChunkIfReady();
    }

    private double CurrentSpeed => (double)speedBox.Value / 100.0;

    private async Task PlayAsync()
    {
        var text = textBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            SetStatus("Please enter text before pressing Play.");
            MessageBox.Show("Paste or type some text first.", "Empty text", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        if (cancellation is not null)
        {
            SetStatus("Speech generation is already running.");
            return;
        }

        StopPlayback();
        CleanupChunks();
        playbackQueue.Clear();
        generationFinished = false;
        cancellation = new CancellationTokenSource();

        SetControlsEnabled(false);
        SetStatus("Preparing speech...");

        try
        {
            await Task.Run(() => GenerateChunks(cancellation.Token));
            File.Copy(TempOutputPath, OutputPath, overwrite: true);
            generationFinished = true;
            SetControlsEnabled(true);
        }
        catch (OperationCanceledException)
        {
            SetStatus("Stopped");
        }
        catch (Exception ex)
        {
            generationFinished = true;
            SetControlsEnabled(true);
            SetStatus("TTS failed.");
            MessageBox.Show(ex.Message, "TTS failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            cancellation?.Dispose();
            cancellation = null;
            File.Delete(TempOutputPath);
        }
    }

    private void GenerateChunks(CancellationToken token)
    {
        Directory.CreateDirectory(ChunkDirectory);
        foreach (var oldChunk in Directory.EnumerateFiles(ChunkDirectory, "chunk_*.mp3"))
        {
            File.Delete(oldChunk);
        }

        var selectedVoice = voices[Ui(() => voiceBox.SelectedItem!.ToString()!)];
        var selectedTone = tones[Ui(() => toneBox.SelectedItem!.ToString()!)];
        var chunks = SplitIntoChunks(CleanText(Ui(() => textBox.Text)));
        if (chunks.Count == 0)
        {
            throw new InvalidOperationException("There is no readable text after removing symbols.");
        }

        using var combined = new FileStream(TempOutputPath, FileMode.Create, FileAccess.Write, FileShare.Read);
        for (var i = 0; i < chunks.Count; i++)
        {
            token.ThrowIfCancellationRequested();
            WaitForQueueSlot(token);

            var chunkPath = Path.Combine(ChunkDirectory, $"chunk_{i:0000}.mp3");
            RunEdgeTts(
                chunks[i],
                selectedVoice,
                SpeedToRate(Ui(() => CurrentSpeed)),
                selectedTone.Pitch,
                selectedTone.Volume,
                chunkPath,
                token);

            token.ThrowIfCancellationRequested();
            var bytes = File.ReadAllBytes(chunkPath);
            combined.Write(bytes, 0, bytes.Length);
            combined.Flush();

            Interlocked.Increment(ref bufferedChunks);
            BeginInvoke((Action)(() =>
            {
                playbackQueue.Enqueue(chunkPath);
                SetControlsEnabled(true);
                PlayNextChunkIfReady();
            }));
        }
    }

    private void RunEdgeTts(
        string text,
        string voice,
        string rate,
        string pitch,
        string volume,
        string outputPath,
        CancellationToken token)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "edge-tts",
            UseShellExecute = false,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
        };

        startInfo.ArgumentList.Add("--text");
        startInfo.ArgumentList.Add(text);
        startInfo.ArgumentList.Add("--voice");
        startInfo.ArgumentList.Add(voice);
        startInfo.ArgumentList.Add("--rate");
        startInfo.ArgumentList.Add(rate);
        startInfo.ArgumentList.Add("--pitch");
        startInfo.ArgumentList.Add(pitch);
        startInfo.ArgumentList.Add("--volume");
        startInfo.ArgumentList.Add(volume);
        startInfo.ArgumentList.Add("--write-media");
        startInfo.ArgumentList.Add(outputPath);

        using var process = Process.Start(startInfo)
            ?? throw new InvalidOperationException("Could not start edge-tts. Install Python and run: pip install edge-tts");

        using var registration = token.Register(() =>
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                }
            }
            catch
            {
                // Best effort cancellation.
            }
        });

        process.WaitForExit();
        token.ThrowIfCancellationRequested();

        if (process.ExitCode != 0)
        {
            var error = process.StandardError.ReadToEnd();
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(error) ? "edge-tts failed." : error);
        }
    }

    private void PlayNextChunkIfReady()
    {
        if (player is not null && player.playState == 3)
        {
            if (!playbackTimer.Enabled)
            {
                playbackTimer.Start();
            }
            return;
        }

        if (playbackQueue.Count == 0)
        {
            if (generationFinished)
            {
                playbackTimer.Stop();
                SetStatus("Finished");
            }
            return;
        }

        var chunkPath = playbackQueue.Dequeue();
        Interlocked.Decrement(ref bufferedChunks);
        try
        {
            EnsurePlayer();
            player!.URL = chunkPath;
            player.settings.rate = CurrentSpeed;
            player.controls.play();
            SetStatus("Playing");
            playbackTimer.Start();
        }
        catch (Exception ex)
        {
            playbackTimer.Stop();
            SetStatus("Playback failed.");
            MessageBox.Show(ex.Message, "Playback failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void EnsurePlayer()
    {
        if (player is not null)
        {
            return;
        }

        var playerType = Type.GetTypeFromProgID("WMPlayer.OCX")
            ?? throw new InvalidOperationException("Windows Media Player is not available.");
        player = Activator.CreateInstance(playerType);
    }

    private void Stop()
    {
        cancellation?.Cancel();
        playbackTimer.Stop();
        playbackQueue.Clear();
        Interlocked.Exchange(ref bufferedChunks, 0);
        generationFinished = true;
        StopPlayback();
        CleanupChunks();
        SetControlsEnabled(true);
        SetStatus("Stopped");
    }

    private void StopPlayback()
    {
        try
        {
            player?.controls.stop();
        }
        catch
        {
            // Best effort: stop should never crash the UI.
        }
    }

    private void WaitForQueueSlot(CancellationToken token)
    {
        while (Volatile.Read(ref bufferedChunks) >= 2)
        {
            token.ThrowIfCancellationRequested();
            Thread.Sleep(50);
        }
    }

    private void CleanupChunks()
    {
        if (!Directory.Exists(ChunkDirectory))
        {
            return;
        }

        foreach (var chunkPath in Directory.EnumerateFiles(ChunkDirectory, "chunk_*.mp3"))
        {
            try
            {
                File.Delete(chunkPath);
            }
            catch
            {
                // Ignore locked chunk cleanup; next run will retry.
            }
        }
    }

    private static string CleanText(string text)
    {
        return ExtraSpaces.Replace(SymbolsToSkip.Replace(text, " "), " ").Trim();
    }

    private static List<string> SplitIntoChunks(string text)
    {
        var chunks = new List<string>();
        var current = "";

        foreach (Match match in SentenceParts.Matches(text))
        {
            var part = match.Value.Trim();
            if (part.Length == 0)
            {
                continue;
            }

            if (part.Length > MaxChunkChars)
            {
                if (current.Length > 0)
                {
                    chunks.Add(current);
                    current = "";
                }
                chunks.AddRange(SplitLongText(part));
                continue;
            }

            var candidate = string.IsNullOrEmpty(current) ? part : $"{current} {part}";
            if (current.Length > 0 && candidate.Length > MaxChunkChars)
            {
                chunks.Add(current);
                current = part;
            }
            else
            {
                current = candidate;
            }
        }

        if (current.Length > 0)
        {
            chunks.Add(current);
        }

        return chunks;
    }

    private static IEnumerable<string> SplitLongText(string text)
    {
        var current = "";
        foreach (var word in text.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            var candidate = string.IsNullOrEmpty(current) ? word : $"{current} {word}";
            if (current.Length > 0 && candidate.Length > MaxChunkChars)
            {
                yield return current;
                current = word;
            }
            else
            {
                current = candidate;
            }
        }

        if (current.Length > 0)
        {
            yield return current;
        }
    }

    private static string SpeedToRate(double speed)
    {
        var percent = (int)Math.Round((speed - 1.0) * 100);
        return percent >= 0 ? $"+{percent}%" : $"{percent}%";
    }

    private void SetControlsEnabled(bool enabled)
    {
        playButton.Enabled = enabled;
        voiceBox.Enabled = enabled;
        toneBox.Enabled = enabled;
    }

    private void SetStatus(string message)
    {
        statusLabel.Text = $"Status: {message}";
    }

    private T Ui<T>(Func<T> read)
    {
        if (!InvokeRequired)
        {
            return read();
        }

        return (T)Invoke(read);
    }
}
