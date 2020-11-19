package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class Log {

    public enum Level {
        VERBOSE, DEBUG, INFO, WARN, ERROR, NONE
    }

    private static volatile boolean isLogEnabled = true;
    private static final Map<String, Level> tagStates = new ConcurrentHashMap<>(128);

    public interface ILogCallback {
        void onLogMessage();
    }

    public static class FormatMsg {
        private final String msg;
        private final Object[] args;

        public FormatMsg(@NonNull String msg, Object... args) {
            this.msg = msg;
            this.args = args;
        }

        @Override
        @NonNull
        public String toString() {
            return StringUtils.formatUS(msg, args);
        }
    }

    public static class Msg {
        private final Object[] msgs;

        public Msg(@NonNull Object... msgs) {
            this.msgs = msgs;
        }

        @Override
        @NonNull
        public String toString() {
            return dumpMsg(msgs);
        }
    }

    private static boolean isActiveTag(@NonNull String tag, @NonNull Level level) {
        Level tagLevel = tagStates.get(tag);
        return tagLevel == null || tagLevel.ordinal() <= level.ordinal();
    }

    public static boolean isEnabledLog() {
        return isLogEnabled;
    }

    public static boolean isEnabledLog(@NonNull String tag, @NonNull Level level) {
        return isLogEnabled && isActiveTag(tag, level);
    }

    public static void setIsLogEnabled(boolean enabled) {
        isLogEnabled = enabled;
    }

    @NonNull
    public static String getNativeStackTrace(@NonNull Throwable t) {
        return android.util.Log.getStackTraceString(t);
    }

    public static List<StackTraceElement> getStackTrace(@NonNull Throwable exception, boolean fullStack) {
        return fullStack ? getFullStackTrace(exception) : getApplicationStackTrace(exception);
    }

    @NonNull
    public static String dumpStackTrace(@NonNull List<StackTraceElement> stackTrace) {
        StringBuilder stackTraceOutput = new StringBuilder(1024);

        for (StackTraceElement element : stackTrace) {
            stackTraceOutput
                    .append("\tat ")
                    .append(element.getClassName())
                    .append('.')
                    .append(element.getMethodName())
                    .append('(')
                    .append(element.getFileName())
                    .append(':')
                    .append(element.getLineNumber())
                    .append(')')
                    .append('\n')
            ;
        }

        return stackTraceOutput.toString();
    }

    @NonNull
    public static List<StackTraceElement> getFullStackTrace(@NonNull Throwable exception) {
        List<StackTraceElement> res = ArrayUtils.toArrayList(exception.getStackTrace());
        if (exception.getCause() != null) {
            res.addAll(getFullStackTrace(exception.getCause()));
        }
        return res;
    }

    @NonNull
    public static List<StackTraceElement> getApplicationStackTrace(@NonNull Throwable exception) {
        return ArrayUtils.filteredArray(getFullStackTrace(exception), item -> {
            String className = item.getClassName();
            return !className.startsWith("android.") && !className.startsWith("com.android.") && !className.startsWith("java.");
        });
    }

    @NonNull
    private static String dumpMsg(@Nullable Object... objects) {
        if (objects == null) {
            return "null";
        }

        switch (objects.length) {
            case 0:
                return "";
            case 1:
                return String.valueOf(objects[0]);
            default:
                StringBuilder b = new StringBuilder(512);
                for (Object item : objects) {
                    b.append(String.valueOf(item));
                }
                return b.toString();
        }
    }

    public static void log(@NonNull ILogCallback logCallback) {
        if (isEnabledLog()) {
            logCallback.onLogMessage();
        }
    }

    @NonNull
    public static FormatMsg format(@NonNull String msg, Object... args) {
        return new FormatMsg(msg, args);
    }

    @NonNull
    public static Msg msg(@NonNull Object... msgs) {
        return new Msg(msgs);
    }

    public static void v(@NonNull String tag, Object... msg) {
        if (isEnabledLog(tag, Level.VERBOSE)) {
            android.util.Log.v(tag, dumpMsg(msg));
        }
    }

    public static void v(@NonNull String tag, @NonNull Object msg, Throwable tr) {
        if (isEnabledLog(tag, Level.VERBOSE)) {
            android.util.Log.v(tag, dumpMsg(msg), tr);
        }
    }

    public static void d(@NonNull String tag, Object... msg) {
        if (isEnabledLog(tag, Level.DEBUG)) {
            android.util.Log.d(tag, dumpMsg(msg));
        }
    }

    public static void d(@NonNull String tag, @NonNull Object msg, Throwable tr) {
        if (isEnabledLog(tag, Level.DEBUG)) {
            android.util.Log.d(tag, dumpMsg(msg), tr);
        }
    }

    public static void i(@NonNull String tag, Object... msg) {
        if (isEnabledLog(tag, Level.INFO)) {
            android.util.Log.i(tag, dumpMsg(msg));
        }
    }

    public static void i(@NonNull String tag, @NonNull Object msg, Throwable tr) {
        if (isEnabledLog(tag, Level.INFO)) {
            android.util.Log.i(tag, dumpMsg(msg), tr);
        }
    }

    public static void w(@NonNull String tag, Object... msg) {
        if (isEnabledLog(tag, Level.WARN)) {
            android.util.Log.w(tag, dumpMsg(msg));
        }
    }

    public static void w(@NonNull String tag, @NonNull Object msg, Throwable tr) {
        if (isEnabledLog(tag, Level.WARN)) {
            android.util.Log.w(tag, dumpMsg(msg), tr);
        }
    }

    public static void w(@NonNull String tag, Throwable tr) {
        if (isEnabledLog(tag, Level.WARN)) {
            android.util.Log.w(tag, tr);
        }
    }

    public static void e(@NonNull String tag, Object... msg) {
        // Always dump error stack to log
        android.util.Log.e(tag, dumpMsg(msg));
    }

    public static void e(@NonNull String tag, @NonNull FormatMsg msg, @NonNull Throwable tr) {
        e(tag, msg.toString(), tr);
    }

    public static void e(@NonNull String tag, @NonNull Throwable tr) {
        // Always dump error stack to log
        android.util.Log.e(tag, tr.getMessage(), tr);
    }

    public static void e(@NonNull String tag, @NonNull Object msg, @NonNull Throwable tr) {
        // Always dump error stack to log
        android.util.Log.e(tag, dumpMsg(msg), tr);
    }

    @NonNull
    public static String getCallStack(@NonNull Throwable exception, boolean fullStack) {
        return dumpStackTrace(getStackTrace(exception, fullStack));
    }

    @NonNull
    public static String getCallStack(boolean fullStack) {
        Exception e = new Exception();
        List<StackTraceElement> stackTrace = getStackTrace(e, fullStack);
        stackTrace.remove(0); // exclude this method
        return dumpStackTrace(stackTrace);
    }

    @NonNull
    public static String getTag(@NonNull Class<?> clazz) {
        return getTag(clazz, Level.VERBOSE);
    }

    @NonNull
    public static String getTag(@NonNull Class<?> clazz, @NonNull Level level) {
        String tag = ClassUtils.getClassTag(clazz).intern();
        tagStates.put(tag, level);
        return tag;
    }

    @NonNull
    public static String getTag(@NonNull Object obj) {
        if (obj.getClass() == String.class) {
            return ClassUtils.cast(obj);
        }
        return StringUtils.concat(ClassUtils.getClassTag(obj.getClass()), "@", String.valueOf(obj.hashCode()));
    }

    @NonNull
    public static String getTag(@NonNull Object obj, @NonNull String suffix) {
        return StringUtils.join(".", getTag(obj), suffix);
    }
}
