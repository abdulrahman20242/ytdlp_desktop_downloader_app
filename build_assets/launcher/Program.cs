using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace YTDownloader.Launcher
{
    /// <summary>
    /// Portable outer launcher that boots the PyInstaller-built core, resolving it
    /// relative to this executable so the app works from any working directory and
    /// after relocation. The parent folder layout is:
    ///
    ///   YT Downloader.exe          <- this launcher
    ///   YT Downloader\YTDownloaderCore.exe
    ///   YT Downloader\_internal\...
    ///   YT Downloader\bin\...
    ///   YT Downloader\assets\...
    ///
    /// Compiled for .NET Framework 4.8, which ships with Windows 10/11, so the
    /// launcher itself has no runtime requirement.
    /// </summary>
    internal static class Program
    {
        private const string CoreFolderName = "YT Downloader";
        private const string CoreExecutableName = "YTDownloaderCore.exe";

        private const uint MB_ICONERROR = 0x00000010;
        private const uint MB_TOPMOST = 0x00040000;

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern int MessageBoxW(
            IntPtr hWnd,
            [MarshalAs(UnmanagedType.LPWStr)] string text,
            [MarshalAs(UnmanagedType.LPWStr)] string caption,
            uint type);

        private static void ShowError(string message)
        {
            _ = MessageBoxW(IntPtr.Zero, message, "YT Downloader", MB_ICONERROR | MB_TOPMOST);
        }

        private static string QuoteArg(string value)
        {
            var sb = new StringBuilder();
            sb.Append('"');
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                int backslashes = 0;
                while (i < value.Length && value[i] == '\\')
                {
                    backslashes++;
                    i++;
                }
                bool atQuote = i < value.Length && value[i] == '"';
                for (int b = 0; b < backslashes; b++)
                {
                    sb.Append(atQuote || i >= value.Length ? "\\\\" : "\\");
                }
                if (atQuote)
                {
                    sb.Append("\\\"");
                }
                else if (i < value.Length)
                {
                    sb.Append(value[i]);
                }
            }
            sb.Append('"');
            return sb.ToString();
        }

        private static int Main(string[] args)
        {
            string launchDir = AppContext.BaseDirectory;
            string coreExe = Path.Combine(launchDir, CoreFolderName, CoreExecutableName);

            if (!File.Exists(coreExe))
            {
                ShowError(
                    "تعذر العثور على مكوّن التطبيق الأساسي:\n" +
                    coreExe + "\n" +
                    "تأكد من وجود مجلد \"" + CoreFolderName + "\" بجانب هذا الملف.");
                return 1;
            }

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = coreExe,
                    WorkingDirectory = launchDir,
                    UseShellExecute = false
                };

                var cmd = new StringBuilder();
                for (int i = 0; i < args.Length; i++)
                {
                    if (i > 0)
                    {
                        cmd.Append(' ');
                    }
                    cmd.Append(QuoteArg(args[i]));
                }
                psi.Arguments = cmd.ToString();

                using (Process core = Process.Start(psi))
                {
                    if (core == null)
                    {
                        ShowError("تعذر تشغيل التطبيق الأساسي.");
                        return 1;
                    }
                    core.WaitForExit();
                    return core.ExitCode;
                }
            }
            catch (Exception ex)
            {
                ShowError("فشل تشغيل التطبيق:\n" + ex.Message);
                return 1;
            }
        }
    }
}