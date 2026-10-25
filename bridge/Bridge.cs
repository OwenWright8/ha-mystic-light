using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

// Tiny HTTP bridge exposing MSI's Mystic Light SDK to Home Assistant.
public static class Bridge
{
    const string D = @"__DLL__";

    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_Initialize();
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_Release();
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetErrorMessage(int code, [MarshalAs(UnmanagedType.BStr)] out string desc);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetDeviceInfo([MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_BSTR)] out string[] types, [MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_BSTR)] out string[] counts);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetDeviceName([MarshalAs(UnmanagedType.BStr)] string type, [MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_BSTR)] out string[] names);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetLedInfo([MarshalAs(UnmanagedType.BStr)] string type, int index, [MarshalAs(UnmanagedType.BStr)] out string name, [MarshalAs(UnmanagedType.SafeArray, SafeArraySubType = VarEnum.VT_BSTR)] out string[] styles);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetLedColor([MarshalAs(UnmanagedType.BStr)] string type, int index, out int r, out int g, out int b);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_GetLedStyle([MarshalAs(UnmanagedType.BStr)] string type, int index, [MarshalAs(UnmanagedType.BStr)] out string style);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_SetLedColor([MarshalAs(UnmanagedType.BStr)] string type, int index, int r, int g, int b);
    [DllImport(D, CallingConvention = CallingConvention.Cdecl)] static extern int MLAPI_SetLedStyle([MarshalAs(UnmanagedType.BStr)] string type, int index, [MarshalAs(UnmanagedType.BStr)] string style);

    const int OK = 0, TIMEOUT = -2, NOT_INITIALIZED = -4, NOT_SUPPORTED = -103;

    class SdkException : Exception
    {
        public readonly int Code;
        public SdkException(string call, int code) : base(call + " failed: " + ErrText(code)) { Code = code; }
        // For errors raised without touching the SDK (it may block while uninitialised).
        public SdkException(int code, string message) : base(message) { Code = code; }
    }

    static readonly object Sdk = new object();
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static bool ready;
    static string token = "";
    static string logPath;

    static void Log(string msg)
    {
        string line = DateTime.Now.ToString("s") + " " + msg;
        Console.WriteLine(line);
        if (logPath == null) return;
        lock (Json) { try { File.AppendAllText(logPath, line + Environment.NewLine); } catch { } }
    }

    static string ErrText(int code)
    {
        string desc = null;
        try { MLAPI_GetErrorMessage(code, out desc); } catch { }
        return code + (string.IsNullOrEmpty(desc) ? "" : " (" + desc + ")");
    }

    static void Check(string call, int code)
    {
        if (code == OK) return;
        if (code == TIMEOUT || code == NOT_INITIALIZED) ready = false;
        throw new SdkException(call, code);
    }

    static DateTime lastInitAttempt = DateTime.MinValue;
    static string lastInitError = "not initialised yet";

    static void EnsureReady()
    {
        if (ready) return;
        // A failed SDK init blocks for over a minute, so don't retry on every request.
        if (DateTime.UtcNow - lastInitAttempt < TimeSpan.FromSeconds(60))
            throw new SdkException(NOT_INITIALIZED, "SDK not ready (" + lastInitError + "); retrying shortly");
        try
        {
            try { MLAPI_Release(); } catch { }
            Check("MLAPI_Initialize", MLAPI_Initialize());
            BuildCatalog();
            ready = true;
            Log("Mystic Light SDK ready (" + catalog.Count + " LED areas)");
        }
        catch (SdkException e) { lastInitError = e.Message; throw; }
        finally { lastInitAttempt = DateTime.UtcNow; }
    }

    class LedInfo { public string Type, DevName, Name; public int Index; public string[] Styles; }

    // Device list, names and style lists never change while the SDK is up, so they are
    // read once per init. Polls then only read style and colour: the array-returning
    // calls are the ones most exposed to the SDK's memory handling.
    static List<LedInfo> catalog = new List<LedInfo>();

    static void BuildCatalog()
    {
        var leds = new List<LedInfo>();
        string[] types, counts;
        Check("MLAPI_GetDeviceInfo", MLAPI_GetDeviceInfo(out types, out counts));
        for (int i = 0; i < types.Length; i++)
        {
            string[] devNames;
            string devName = MLAPI_GetDeviceName(types[i], out devNames) == OK && devNames != null && devNames.Length > 0 ? devNames[0] : types[i];
            int n;
            int.TryParse(counts[i], out n);
            for (int j = 0; j < n; j++)
            {
                string name;
                string[] styles;
                Check("MLAPI_GetLedInfo", MLAPI_GetLedInfo(types[i], j, out name, out styles));
                leds.Add(new LedInfo { Type = types[i], Index = j, DevName = devName, Name = name ?? (types[i] + " " + j), Styles = styles ?? new string[0] });
            }
        }
        catalog = leds;
    }

    static List<Dictionary<string, object>> ListLeds()
    {
        var result = new List<Dictionary<string, object>>();
        foreach (var led in catalog) result.Add(ReadLed(led));
        return result;
    }

    static LedInfo FindLed(string type, int index)
    {
        foreach (var led in catalog) if (led.Type == type && led.Index == index) return led;
        throw new ArgumentException("Unknown LED " + type + "[" + index + "]");
    }

    static Dictionary<string, object> ReadLed(LedInfo led)
    {
        string style;
        int r, g, b;
        int res = MLAPI_GetLedStyle(led.Type, led.Index, out style);
        if (res == TIMEOUT || res == NOT_INITIALIZED) Check("MLAPI_GetLedStyle", res);
        if (res != OK) style = "";
        if (MLAPI_GetLedColor(led.Type, led.Index, out r, out g, out b) != OK) { r = g = b = 0; }
        return new Dictionary<string, object> {
            { "id", led.Type + "_" + led.Index }, { "type", led.Type }, { "index", led.Index },
            { "device_name", led.DevName }, { "name", led.Name },
            { "style", style ?? "" }, { "styles", led.Styles },
            { "rgb", new[] { r, g, b } },
        };
    }

    static Dictionary<string, object> SetLed(string type, int index, Dictionary<string, object> body)
    {
        LedInfo led = FindLed(type, index);
        object style, rgb, fallback;
        if (body.TryGetValue("style", out style) && style != null)
            Check("MLAPI_SetLedStyle", MLAPI_SetLedStyle(type, index, style.ToString()));
        if (body.TryGetValue("rgb", out rgb) && rgb is IList)
        {
            var c = (IList)rgb;
            int r = Convert.ToInt32(c[0]), g = Convert.ToInt32(c[1]), b = Convert.ToInt32(c[2]);
            int res = MLAPI_SetLedColor(type, index, r, g, b);
            if (res == NOT_SUPPORTED && body.TryGetValue("fallback_style", out fallback) && fallback != null)
            {
                // Current style ignores colour (e.g. Rainbow): switch to a solid style and retry.
                Check("MLAPI_SetLedStyle", MLAPI_SetLedStyle(type, index, fallback.ToString()));
                res = MLAPI_SetLedColor(type, index, r, g, b);
            }
            if (res != NOT_SUPPORTED) Check("MLAPI_SetLedColor", res);
        }
        return ReadLed(led);
    }

    public static void Run(int port, string authToken, string logFile)
    {
        token = authToken ?? "";
        logPath = logFile;
        var listener = new TcpListener(IPAddress.Any, port);
        listener.Start();
        Log("Listening on port " + port);
        lock (Sdk) { try { EnsureReady(); } catch (Exception e) { Log(e.Message); } }
        // Requests are served one at a time on this thread so every SDK call
        // happens on the thread that initialised it.
        while (true) Handle(listener.AcceptTcpClient());
    }

    static void Handle(TcpClient client)
    {
        using (client)
        {
            try
            {
                client.ReceiveTimeout = 10000;
                var stream = client.GetStream();
                var reader = new StreamReader(stream, Encoding.UTF8);
                string requestLine = reader.ReadLine();
                if (string.IsNullOrEmpty(requestLine)) return;
                string[] parts = requestLine.Split(' ');
                string method = parts[0], path = parts.Length > 1 ? parts[1].Split('?')[0] : "/";
                var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                string line;
                while (!string.IsNullOrEmpty(line = reader.ReadLine()))
                {
                    int colon = line.IndexOf(':');
                    if (colon > 0) headers[line.Substring(0, colon).Trim()] = line.Substring(colon + 1).Trim();
                }
                string body = "";
                string lenText;
                if (headers.TryGetValue("Content-Length", out lenText))
                {
                    int len = Math.Min(int.Parse(lenText), 65536);
                    var buf = new char[len];
                    int read = 0;
                    while (read < len) { int n = reader.Read(buf, read, len - read); if (n <= 0) break; read += n; }
                    body = new string(buf, 0, read);
                }

                int status;
                object payload = Route(method, path, headers, body, out status);
                Respond(stream, status, payload);
            }
            catch (Exception e) { Log("Request error: " + e.Message); }
        }
    }

    static object Route(string method, string path, Dictionary<string, string> headers, string body, out int status)
    {
        status = 200;
        string auth;
        if (token.Length > 0 && (!headers.TryGetValue("Authorization", out auth) || auth != "Bearer " + token))
        {
            status = 401;
            return new Dictionary<string, object> { { "error", "unauthorized" } };
        }
        string[] seg = path.Trim('/').Split('/');
        try
        {
            lock (Sdk)
            {
                if (method == "GET" && path == "/api/health")
                {
                    return new Dictionary<string, object> { { "ok", true }, { "sdk_ready", ready }, { "sdk_error", ready ? null : lastInitError } };
                }
                if (method == "GET" && path == "/api/leds")
                {
                    EnsureReady();
                    return ListLeds();
                }
                if (method == "POST" && seg.Length == 4 && seg[0] == "api" && seg[1] == "leds")
                {
                    EnsureReady();
                    var req = Json.Deserialize<Dictionary<string, object>>(body == "" ? "{}" : body);
                    string type = Uri.UnescapeDataString(seg[2]);
                    Log("Set " + type + "[" + seg[3] + "] " + body);
                    return SetLed(type, int.Parse(seg[3]), req);
                }
            }
            status = 404;
            return new Dictionary<string, object> { { "error", "not found" } };
        }
        catch (SdkException e)
        {
            Log(e.Message);
            status = 502;
            return new Dictionary<string, object> { { "error", e.Message }, { "code", e.Code } };
        }
        catch (Exception e)
        {
            Log(e.ToString());
            status = 400;
            return new Dictionary<string, object> { { "error", e.Message } };
        }
    }

    static void Respond(NetworkStream stream, int status, object payload)
    {
        byte[] data = Encoding.UTF8.GetBytes(Json.Serialize(payload));
        string reason = status == 200 ? "OK" : status == 401 ? "Unauthorized" : status == 404 ? "Not Found" : status == 502 ? "Bad Gateway" : "Bad Request";
        byte[] head = Encoding.ASCII.GetBytes("HTTP/1.1 " + status + " " + reason + "\r\nContent-Type: application/json\r\nContent-Length: " + data.Length + "\r\nConnection: close\r\n\r\n");
        stream.Write(head, 0, head.Length);
        stream.Write(data, 0, data.Length);
        stream.Flush();
    }
}
