using System.Text.RegularExpressions;

namespace MonmusuMod.Core;

// Same ordered token contract as tools/novel_workflow.py; no text normalization/reflow.
public static class ControlTokens
{
    static readonly Regex TagStart = new(@"</?[A-Za-z][A-Za-z0-9_:-]*(?=[\s=/>]|$)");
    static readonly Regex Token = new(@"\r\n|\r|\n|\\[nr]|\$\{[^{}\r\n]+\}|\{[A-Za-z_0-9][^{}\r\n]*\}|%(?:[0-9]+\$)?[sdif]|\$[A-Za-z_][A-Za-z_0-9]*|■+");
    public static List<string> Read(string text)
    {
        var result = new List<string>();
        for (int index = 0; index < text.Length;)
        {
            var start = TagStart.Match(text, index);
            if (start.Success && start.Index == index)
            {
                int end = index + 1; char quote = '\0';
                for (; end < text.Length; end++)
                {
                    char ch = text[end];
                    if (quote != '\0') { if (ch == quote) quote = '\0'; }
                    else if (ch is '\'' or '"') quote = ch;
                    else if (ch is '<' or '>') break;
                }
                if (end == text.Length || text[end] != '>' || quote != '\0') throw new InvalidDataException("Malformed markup");
                result.Add(text.Substring(index, end + 1 - index)); index = end + 1;
            }
            else
            {
                var token = Token.Match(text, index);
                if (token.Success && token.Index == index) { result.Add(token.Value); index += token.Length; }
                else index++;
            }
        }
        return result;
    }
}
