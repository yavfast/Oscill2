package com.oscill.utils;

import android.os.ConditionVariable;
import android.os.Handler;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.IAsyncTask;

import java.util.ArrayList;

public class ExceptionWrapper implements IAsyncTask, Runnable {

    private static final String TAG = "ExceptionWrapper";

    private static final int WARN_UI_TIMEOUT = 100L;
    private static final int WARN_BG_TIMEOUT = 5000L;

    public interface ExceptionCallback {
        void onException(@NonNull Throwable e);
    }

    private static final ArrayList<ExceptionCallback> callbacks = new ArrayList<>();

    private final StackException stackException;
    private final Runnable runnable;
    private final Handler handler;
    private final ConditionVariable completed = new ConditionVariable();
    private int started;

    public ExceptionWrapper(@NonNull Runnable runnable) {
        this(runnable, null);
    }

    public ExceptionWrapper(@NonNull Runnable runnable, @Nullable Handler handler) {
        this.stackException = new StackException();
        this.runnable = runnable;
        this.handler = handler;
    }

    @Override
    public void run() {
        started = SystemClock.uptimeMillis();
        try {
            // Fix many requests from handler
            if (handler != null) {
                handler.removeCallbacks(this);
            }

            runnable.run();

            checkExecutionTime();
        } catch (Throwable e) {
            StackTraceElement[] stack = stackException.getStackTrace();
            if (stack != null && stack.length > 2) {
                e.setStackTrace(ArrayUtils.join(e.getStackTrace(), ArrayUtils.subArray(stack, 2, stack.length)));
            }

            processException(e);

            throw e;
        } finally {
            completed.open();
        }
    }

    @Override
    public void await() {
        completed.block();
    }

    public static void addExceptionCallback(@NonNull ExceptionCallback callback) {
        synchronized (callbacks) {
            callbacks.add(callback);
        }
    }

    private static void processException(@NonNull Throwable e) {
        Log.e(TAG, e);

        synchronized (callbacks) {
            for (ExceptionCallback callback : callbacks) {
                callback.onException(e);
            }
        }
    }

    private void checkExecutionTime() {
        if (Log.isEnabledLog()) {
            int time = SystemClock.uptimeMillis() - started;
            boolean isTimeout = (time > (Executor.isUIThread() ? WARN_UI_TIMEOUT : WARN_BG_TIMEOUT));
            if (isTimeout) {
                Log.w(TAG, Log.msg("Long task execution ", (Executor.isUIThread() ? "[UI Thread] " : ""), ": ", time, "ms"), stackException);
            }
        }
    }

}
