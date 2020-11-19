package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.nio.charset.Charset;
import java.util.List;
import java.util.Locale;

@SuppressWarnings("StringEquality")
public class StringUtils {

    public static final String EMPTY = "";

    public static final Charset UTF_8 = Charset.forName("UTF-8");

    /**
     * Fastest implementation for String
     **/

    public static boolean equals(@Nullable String str1, @Nullable String str2) {
        return str1 == str2 || (str1 != null && str2 != null && str1.length() == str2.length() && str1.compareTo(str2) == 0);
    }

    public static boolean equalsIgnoreCase(@Nullable String str1, @Nullable String str2) {
        return str1 != null && str1.equalsIgnoreCase(str2);
    }

    public static boolean startsWithIgnoreCase(@Nullable String str, @Nullable String subStr) {
        return str == subStr || (str != null && subStr != null && str.regionMatches(true, 0, subStr, 0, subStr.length()));
    }

    public static boolean startsWith(@Nullable String str, @Nullable String subStr) {
        return str == subStr || (str != null && subStr != null && str.startsWith(subStr));
    }

    public static boolean contains(@Nullable String str, @Nullable String subStr) {
        return str == subStr || (str != null && subStr != null && str.contains(subStr));
    }

    public static boolean containsIgnoreCase(@Nullable String str, @Nullable String subStr) {
        if (str == null || subStr == null) return false;
        if (str == subStr) return true;

        int len = subStr.length();
        int max = str.length() - len;
        for (int i = 0; i <= max; i++) {
            if (str.regionMatches(true, i, subStr, 0, len)) {
                return true;
            }
        }
        return false;
    }

    public static boolean endWith(@Nullable String str, char ch) {
        return str != null && !str.isEmpty() && str.charAt(str.length() - 1) == ch;
    }

    public static boolean endWith(@Nullable String str, @NonNull String suffix) {
        return str != null && str.endsWith(suffix);
    }

    public static int indexOf(@Nullable String str, @Nullable String subStr) {
        if (isEmpty(str) || isEmpty(subStr)) {
            return -1;
        }

        if (subStr.length() == 1) {
            return str.lastIndexOf(subStr.charAt(0));
        }
        return str.lastIndexOf(subStr);
    }

    public int lastIndexOf(@NonNull String str, @NonNull String subStr) {
        if (subStr.length() == 1) {
            return str.lastIndexOf(subStr.charAt(0));
        }
        return str.lastIndexOf(subStr);
    }

    public int lastIndexOf(@NonNull String str, char ch) {
        return str.lastIndexOf(ch);
    }

    @NonNull
    public static String trimRight(@Nullable String str) {
        if (isNotEmpty(str)) {
            int len = str.length();
            while (len > 0 && (str.charAt(len - 1) <= ' ')) {
                len--;
            }
            return len < str.length() ? str.substring(0, len) : str;
        }

        return EMPTY;
    }

    @NonNull
    public static String trim(@Nullable String str) {
        if (isNotEmpty(str)) {
            int len = str.length();
            int st = 0;

            while ((st < len) && (str.charAt(st) <= ' ')) {
                st++;
            }
            while ((st < len) && (str.charAt(len - 1) <= ' ')) {
                len--;
            }
            return ((st > 0) || (len < str.length())) ? str.substring(st, len) : str;
        }
        return EMPTY;
    }

    @NonNull
    public static String trim(@Nullable String str, @NonNull String trimChars) {
        if (isNotEmpty(str)) {
            int len = str.length();
            int st = 0;

            while ((st < len) && trimChars.indexOf(str.charAt(st)) >= 0) {
                st++;
            }
            while ((st < len) && trimChars.indexOf(str.charAt(len - 1)) >= 0) {
                len--;
            }
            return ((st > 0) || (len < str.length())) ? str.substring(st, len) : str;
        }
        return EMPTY;
    }

    @NonNull
    public static String upperFirstChar(@Nullable String str) {
        if (isNotEmpty(str)) {
            char[] stringArray = str.toCharArray();
            stringArray[0] = Character.toUpperCase(stringArray[0]);
            return new String(stringArray);
        }
        return EMPTY;
    }

    public static boolean isEmpty(@Nullable String str) {
        return str == null || str.isEmpty();
    }

    public static boolean isNotEmpty(@Nullable String str) {
        return str != null && !str.isEmpty();
    }

    @NonNull
    public static String toLowerCase(@NonNull String str) {
        if (isNotEmpty(str)) {
            char[] stringArray = str.toCharArray();
            boolean strChanged = false;
            int ch;
            int chLow;
            for (int idx = 0; idx < stringArray.length; idx++) {
                ch = stringArray[idx];
                chLow = Character.toLowerCase(ch);
                if (ch != chLow) {
                    strChanged = true;
                    stringArray[idx] = (char) chLow;
                }
            }
            if (strChanged) {
                return new String(stringArray);
            }
        }
        return str;
    }

    @NonNull
    public static String toUpperCase(@NonNull String str) {
        if (isNotEmpty(str)) {
            char[] stringArray = str.toCharArray();
            boolean strChanged = false;
            int ch;
            int chLow;
            for (int idx = 0; idx < stringArray.length; idx++) {
                ch = stringArray[idx];
                chLow = Character.toUpperCase(ch);
                if (ch != chLow) {
                    strChanged = true;
                    stringArray[idx] = (char) chLow;
                }
            }
            if (strChanged) {
                return new String(stringArray);
            }
        }
        return str;
    }

    @Nullable
    public static String[] split(@Nullable String str, @NonNull String delimiter) {
        return isNotEmpty(str) ? str.split(delimiter) : null;
    }

    @NonNull
    public static String join(@NonNull String delimiter, @NonNull List<String> tokens) {
        return join(delimiter, ArrayUtils.toArray(tokens, String.class));
    }

    @NonNull
    public static String join(@NonNull String delimiter, @NonNull String... tokens) {
        if (!ArrayUtils.isEmpty(tokens)) {
            StringBuilder sb = new StringBuilder(1024);
            boolean firstTime = true;
            for (String token : tokens) {
                if (firstTime) {
                    firstTime = false;
                } else {
                    sb.append(delimiter);
                }
                sb.append(token);
            }
            return sb.toString();
        }
        return EMPTY;
    }

    @NonNull
    public static String concat(@NonNull String... tokens) {
        if (!ArrayUtils.isEmpty(tokens)) {
            StringBuilder sb = new StringBuilder(1024);
            for (String token : tokens) {
                sb.append(token);
            }
            return sb.toString();
        }
        return EMPTY;
    }

    @NonNull
    public static String concatIf(@NonNull String baseStr, boolean condition, @NonNull String... tokens) {
        if (condition) {
            return concat(ArrayUtils.join(ArrayUtils.toArray(baseStr), tokens));
        }
        return baseStr;
    }

    @NonNull
    public static String trimQuotes(@NonNull String value) {
        value = value.trim();
        int length = value.length();
        if (length >= 2) {
            char quoteSymbol = value.charAt(0);
            switch (quoteSymbol) {
                case '\'':
                case '\"':
                    int nextQuoteIdx = value.indexOf(quoteSymbol, 1);
                    if (nextQuoteIdx == length - 1) {
                        String innerValue = value.substring(1, length - 1);
                        return trimQuotes(innerValue);
                    }
            }
        }
        return value;
    }

    @NonNull
    public static String padLeft(@NonNull String str, int length, char padChar) {
        int padCount = length - str.length();
        if (padCount > 0) {
            String[] res = new String[padCount + 1];
            String padCharStr = String.valueOf(padChar);
            for (int idx = 0; idx < padCount; idx++) {
                res[idx] = padCharStr;
            }
            res[padCount] = str;
            return concat(res);
        }
        return str;
    }

    @Nullable
    public static String subString(@Nullable String str, int fromIdx) {
        if (isNotEmpty(str) && fromIdx >= 0) {
            return str.substring(fromIdx);
        }

        return str;
    }

    @NonNull
    public static String concatWith(@Nullable String a, @Nullable String b, @NonNull String middle) {
        boolean hasA = isNotEmpty(a);
        boolean hasB = isNotEmpty(b);
        if (hasA && hasB) {
            return concat(a, " ", middle, " ", b);
        } else if (hasA) {
            return a;
        } else if (hasB) {
            return b;
        } else {
            return EMPTY;
        }
    }

    @Nullable
    public static String getFirstLetter(@Nullable String text) {
        return isNotEmpty(text) ? text.substring(0, 1) : null;
    }

    @Nullable
    public static String getFirstLetterUpper(@Nullable String text) {
        return isNotEmpty(text) ? toUpperCase(text.substring(0, 1)) : null;
    }

    public static int compareTo(@Nullable String str1, @Nullable String str2) {
        if ((str1 == null && str2 == null) || str1 == str2) {
            return 0;
        } else if (str1 == null) {
            return -1;
        } else if (str2 == null) {
            return 1;
        }
        return str1.compareTo(str2);
    }

    public static int compareToIgnoreCase(@Nullable String str1, @Nullable String str2) {
        if ((str1 == null && str2 == null) || str1 == str2) {
            return 0;
        } else if (str1 == null) {
            return -1;
        } else if (str2 == null) {
            return 1;
        }
        return str1.compareToIgnoreCase(str2);
    }

    @NonNull
    public static String formatUS(@NonNull String format, @Nullable Object... args) {
        return String.format(Locale.US, format, args);
    }

    @NonNull
    public static String format(@NonNull String format, @Nullable Object... args) {
        return String.format(Locale.getDefault(), format, args);
    }

}
