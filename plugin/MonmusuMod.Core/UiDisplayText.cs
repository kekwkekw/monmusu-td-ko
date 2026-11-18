using System.Text.RegularExpressions;

namespace MonmusuMod.Core;

public static class UiDisplayText
{
    public static bool ContainsHangul(string? value) => value != null && value.Any(ch =>
        ch is >= '\uAC00' and <= '\uD7A3' or >= '\u1100' and <= '\u11FF' or >= '\u3130' and <= '\u318F');

    // These are executable DateTime formats, not prose. Restrict recognition to
    // an entire numeric date/time pattern with at least one separator.
    public static bool IsDateFormat(string value) => Regex.IsMatch(value,
        @"^(?:yyyy|yy|MM|M|dd|d|HH|H|hh|h|mm|m|ss|s)(?:[/ :.-](?:yyyy|yy|MM|M|dd|d|HH|H|hh|h|mm|m|ss|s))+$");

    public static string Render(string value, string path, Func<string, string?> translate)
    {
        value = CompactWeapon(value, path);
        if (path.EndsWith("/SeasonPassButton/RemainDate/Remain", StringComparison.Ordinal))
        {
            var match = Regex.Match(value, @"^(\d{1,2})日まで$");
            if (match.Success && translate("{0}日まで") is { } template)
                return template.Replace("{0}", match.Groups[1].Value, StringComparison.Ordinal);
        }
        if (path.Contains("/BattleLogBanner(Clone)/", StringComparison.Ordinal) && path.EndsWith("/TopArea/Date", StringComparison.Ordinal))
        {
            var match = Regex.Match(value, @"^(\d{4})年(\d{1,2})月(\d{1,2})日$");
            if (match.Success) return $"{match.Groups[1].Value}-{match.Groups[2].Value.PadLeft(2, '0')}-{match.Groups[3].Value.PadLeft(2, '0')}";
        }
        if ((path.Contains("/Section(Clone)/", StringComparison.Ordinal) || path.Contains("/SectionLong(Clone)/", StringComparison.Ordinal))
            && path.EndsWith("/ProgressText", StringComparison.Ordinal))
            return value == "진행도\n" ? "진행\n" : value == "진행도" ? "진행" : value;
        if (path.EndsWith("/RecomDaughterLV/Title", StringComparison.Ordinal))
        {
            string plain = Regex.Replace(value, @"</?cspace(?:=[^>]+)?>", "");
            if (plain == "권장 몬스터 소녀Lv:") return "권장 Lv:";
        }
        if (path.Contains("/Ranch_View(Clone)/", StringComparison.Ordinal) && path.EndsWith("/ExpTextRoot/TitleText", StringComparison.Ordinal)
            && value == "몬스터 소녀 EXP  :") return "유닛 EXP :";
        return value;
    }
    // Used only for cUnitStatusDialog.m_tribeTextPrefix, before the game
    // concatenates the translated ability name. Preserve markup/punctuation.
    public static string TribePrefix(string value, Func<string, string?> translate)
    {
        var match = Regex.Match(value, @"^(?<lead>(?:\s|<[^>]+>)*)種族特性(?=\s|[:：<]|$)");
        if (!match.Success || translate("種族特性") is not { } ko) return value;
        int start = match.Groups["lead"].Length;
        return value[..start] + ko + value[(start + "種族特性".Length)..];
    }

    // Compatibility with the pre-correction CDN. Only this compact label is
    // shortened; other occurrences of the same Korean phrase stay unchanged.
    public static string CompactWeapon(string value, string path) =>
        path.EndsWith("/Unit_StatusView/Class/WeaponTypeNameBase/WeaponTypeNameTitle", StringComparison.Ordinal)
        && value == "무기 종류 :" ? "무기 :" : value;
}
