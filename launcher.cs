using System;
using System.Diagnostics;
using System.IO;
using System.Drawing;
using System.Runtime.InteropServices;

class Launcher
{
    [DllImport("kernel32.dll")]
    static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

    const uint WM_SETICON = 0x0080;
    const int ICON_SMALL = 0;
    const int ICON_BIG = 1;

    static void SetConsoleIcon(string iconPath)
    {
        IntPtr hWnd = GetConsoleWindow();
        if (hWnd == IntPtr.Zero) return;

        using (Icon icon = new Icon(iconPath))
        {
            SendMessage(hWnd, WM_SETICON, (IntPtr)ICON_SMALL, icon.Handle);
            SendMessage(hWnd, WM_SETICON, (IntPtr)ICON_BIG, icon.Handle);
        }
    }

    static int Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string ico = Path.Combine(dir, "silero.ico");

        try { SetConsoleIcon(ico); } catch { /* не критично */ }

        string py  = Path.Combine(dir, ".venv", "Scripts", "python.exe");
        string run = Path.Combine(dir, "run_tts.py");

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = py;
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.Arguments = "\"" + run + "\"" + (args.Length > 0 ? " " + JoinArgs(args) : "");

        Process p = Process.Start(psi);
        p.WaitForExit();
        return p.ExitCode;
    }

    static string JoinArgs(string[] args)
    {
        string[] q = new string[args.Length];
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i] ?? "";
            if (a.Length == 0 || a.IndexOfAny(new[] { ' ', '\t', '"' }) >= 0)
                q[i] = "\"" + a.Replace("\"", "\\\"") + "\"";
            else
                q[i] = a;
        }
        return string.Join(" ", q);
    }
}