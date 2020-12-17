package com.oscill.utils.executor;

import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.ClassUtils;
import com.oscill.utils.ExceptionWrapper;
import com.oscill.utils.Log;
import com.oscill.utils.ObjectUtils;
import com.oscill.types.SuspendValue;
import com.oscill.utils.executor.runnable.IRunnableOnView;
import com.oscill.utils.executor.runnable.RunnableOnView;

import java.lang.ref.WeakReference;
import java.util.concurrent.Callable;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public class Executor {

    private static final String TAG = Log.getTag(Executor.class);

    private static final SuspendValue<Handler> sUIThreadHandler = new SuspendValue<>(() ->
            new Handler(Looper.getMainLooper())
    );

    private static final SuspendValue<ScheduledThreadPoolExecutor> sTaskQueueExecutor = new SuspendValue<>(() -> {
        ScheduledThreadPoolExecutor res = new ScheduledThreadPoolExecutor(1, r -> new Thread(r, "TaskQueueThread"));
        res.setMaximumPoolSize(1);
        return res;
    });

    private static final SuspendValue<ScheduledThreadPoolExecutor> sSyncQueueExecutor = new SuspendValue<>(() -> {
        ScheduledThreadPoolExecutor res = new ScheduledThreadPoolExecutor(1, r -> new Thread(r, "SyncQueueThread"));
        res.setMaximumPoolSize(1);
        return res;
    });

    private static final SuspendValue<ScheduledThreadPoolExecutor> sBackgroundExecutor = new SuspendValue<>(() -> {
        // http://www.bigsoft.co.uk/blog/index.php/2009/11/27/rulepush_grouped_texts-of-a-threadpoolexecutor-pool-size
        final int CPU_COUNT = Runtime.getRuntime().availableProcessors();
        final int CORE_POOL_SIZE = Math.max(4, Math.min(CPU_COUNT, 4));
        final int MAXIMUM_POOL_SIZE = CPU_COUNT * 4 + 1;
        final int KEEP_ALIVE = 60; // timeout for pool threads

        ThreadFactory threadFactory = new ThreadFactory() {
            private final AtomicInteger mCount = new AtomicInteger(1);

            public Thread newThread(@NonNull Runnable r) {
                return new Thread(r, "BackgroundThread #" + mCount.getAndIncrement());
            }
        };

        ScheduledThreadPoolExecutor res = new ScheduledThreadPoolExecutor(CORE_POOL_SIZE, threadFactory);
        res.setMaximumPoolSize(MAXIMUM_POOL_SIZE);
        res.setKeepAliveTime(KEEP_ALIVE, TimeUnit.SECONDS);
        res.allowCoreThreadTimeOut(true);

        fixAsyncTaskExecutor(res);

        return res;
    });

    private static void fixAsyncTaskExecutor(@NonNull ScheduledThreadPoolExecutor executor) {
        if (ClassUtils.setStaticFieldValue(android.os.AsyncTask.class.getName(), "THREAD_POOL_EXECUTOR", executor)) {
            Log.w(TAG, "AsyncTask.THREAD_POOL_EXECUTOR fixed");
        }

        if (ClassUtils.setStaticFieldValue("androidx.loader.content.ModernAsyncTask", "THREAD_POOL_EXECUTOR", executor)) {
            Log.w(TAG, "ModernAsyncTask.THREAD_POOL_EXECUTOR fixed");
        }
    }

    @NonNull
    public static ScheduledThreadPoolExecutor getBackgroundExecutor() {
        return sBackgroundExecutor.get();
    }

    @NonNull
    public static ScheduledThreadPoolExecutor getTaskQueueExecutor() {
        return sTaskQueueExecutor.get();
    }

    @NonNull
    public static ScheduledThreadPoolExecutor getSyncQueueExecutor() {
        return sSyncQueueExecutor.get();
    }

    @NonNull
    public static Handler getMainHandler() {
        return sUIThreadHandler.get();
    }

    public static boolean isUIThread() {
        return Thread.currentThread() == Looper.getMainLooper().getThread();
    }

    public static IAsyncTask runInUIThread(@NonNull Runnable runnable) {
        if (isUIThread()) {
            return runInCurrentThread(runnable);
        } else {
            return runInUIThreadAsync(runnable, 0L);
        }
    }

    public static <T> IAsyncTask runInUIThread(T view, @NonNull IRunnableOnView<T> runnable) {
        return runInUIThread(new RunnableOnView<T>(view) {
            public void run(@NonNull T view) {
                runnable.run(view);
            }
        });
    }

    public static <T> IAsyncTask runInUIThreadAsync(T view, @NonNull IRunnableOnView<T> runnable) {
        return runInUIThreadAsync(view, runnable, 0L);
    }

    public static <T> IAsyncTask runInUIThreadAsync(T view, @NonNull IRunnableOnView<T> runnable, long delay) {
        return runInUIThreadAsync(new RunnableOnView<T>(view) {
            public void run(@NonNull T view) {
                runnable.run(view);
            }
        }, delay);
    }

    public static IAsyncTask runInUIThreadAsync(@NonNull Runnable runnable) {
        return runInUIThreadAsync(runnable, 0L);
    }

    public static IAsyncTask runInUIThreadAsync(@NonNull Runnable runnable, long delay) {
        ExceptionWrapper wrapper = new ExceptionWrapper(runnable, getMainHandler());
        runInTaskQueue(() -> getMainHandler().postDelayed(wrapper, delay), 0L);
        return wrapper;
    }

    public static void runInSyncQueue(@NonNull Runnable runnable) {
        getSyncQueueExecutor().schedule(new ExceptionWrapper(runnable), 0L, TimeUnit.MILLISECONDS);
    }

    public static void runInSyncQueue(@NonNull Runnable runnable, long delay) {
        getSyncQueueExecutor().schedule(new ExceptionWrapper(runnable), delay, TimeUnit.MILLISECONDS);
    }

    public static IAsyncTask runInBackground(@NonNull Runnable runnable) {
        if (isUIThread()) {
            return runInBackgroundAsync(runnable, 0L);
        } else {
            return runInCurrentThread(runnable);
        }
    }

    public static IAsyncTask runInBackgroundAsync(@NonNull Runnable runnable) {
        return runInBackgroundAsync(runnable, 0L);
    }

    public static IAsyncTask runInBackgroundAsync(@NonNull Runnable runnable, long delay) {
        return new AsyncTask<>(getBackgroundExecutor().schedule(new ExceptionWrapper(runnable), delay, TimeUnit.MILLISECONDS));
    }

    public static <V> AsyncTask<V> getInBackgroundAsync(@NonNull Callable<V> callable) {
        return getInBackgroundAsync(callable, 0L);
    }

    public static <V> AsyncTask<V> getInBackgroundAsync(@NonNull Callable<V> callable, long delay) {
        return new AsyncTask<>(getBackgroundExecutor().schedule(callable, delay, TimeUnit.MILLISECONDS));
    }

    public static IAsyncTask runInCurrentThread(@NonNull Runnable runnable) {
        ExceptionWrapper wrapper = new ExceptionWrapper(runnable);
        wrapper.run();
        return wrapper;
    }

    public static void runInTaskQueue(@NonNull Runnable runnable) {
        runInTaskQueue(runnable, 0L);
    }

    public static void runInTaskQueue(@NonNull Runnable runnable, long delay) {
        getTaskQueueExecutor().schedule(runnable, delay, TimeUnit.MILLISECONDS);
    }

/*
    public static void runInUIThreadThrottle(@NonNull Runnable runnable, @NonNull String tag, int throttle) {
        ThrottleTask throttleTask = ThrottleController.getThrottleTask(tag);
        throttleTask.execute(runnable, throttle);
    }
*/

/*
    public static <T> void runInUIThreadThrottle(T view, @NonNull IRunnableOnView<T> runnable, @NonNull String tag, int throttle) {
        runInUIThreadThrottle(new RunnableOnView<T>(view) {
            public void run(@NonNull T view) {
                runnable.run(view);
            }
        }, tag, throttle);
    }
*/

/*
    public static void runInBackgroundThrottle(@NonNull Runnable runnable, @NonNull String tag, int throttle) {
        runInUIThreadThrottle(() -> runInBackgroundAsync(runnable), tag, throttle);
    }
*/

    public static void sleep(long timeMs) {
        if (isUIThread()) {
            dumpCurrentStack("Sleep in UI thread", true);
        }
        SystemClock.sleep(timeMs);
    }

    public static <T> void doWith(@NonNull T obj, @NonNull ObjRunnable<T> runnableIfExists) {
        runnableIfExists.run(obj);
    }

    public static <T> boolean doIfExists(@Nullable T obj, @NonNull ObjRunnable<T> runnableIfExists) {
        // Код не изменять!!!
        if (obj != null) {
            runnableIfExists.run(obj);
            return true;
        }
        return false;
    }

    public static <T> boolean doIfExists(@Nullable T obj, @NonNull ObjRunnable<T> runnableIfExists, @Nullable Runnable runnableIfNotExists) {
        if (obj != null) {
            runnableIfExists.run(obj);
            return true;
        }
        if (runnableIfNotExists != null) {
            runnableIfNotExists.run();
        }
        return false;
    }

    public static <T1,T2> boolean doIfExists(@Nullable T1 obj1, @Nullable T2 obj2, @NonNull ObjRunnable2<T1,T2> runnableIfExists) {
        if (obj1 != null && obj2 != null) {
            runnableIfExists.run(obj1, obj2);
            return true;
        }
        return false;
    }

    public static <T> boolean doIfExistsRef(@Nullable WeakReference<T> objRef, @NonNull ObjRunnable<T> runnableIfExists) {
        if (objRef != null) {
            return doIfExists(objRef.get(), runnableIfExists);
        }
        return false;
    }

    public static <T> IAsyncTask doIfExistsInUIAsync(T obj, @NonNull ObjRunnable<T> runnableIfExists) {
        return getIfExists(obj, obj1 -> runInUIThreadAsync(() -> runnableIfExists.run(obj1)));
    }

    public static <T> IAsyncTask doIfExistsInUI(T obj, @NonNull ObjRunnable<T> runnableIfExists) {
        return getIfExists(obj, obj1 -> runInUIThread(() -> runnableIfExists.run(obj1)));
    }

/*
    public static <T> boolean doIfNotEmpty(@Nullable T obj, @NonNull ObjRunnable<T> runnableIfNotEmpty) {
        if (obj != null) {
            boolean isEmpty = from(obj, Boolean.class)
                    .ifCast(String.class, String::isEmpty)
                    .ifCast(Collection.class, Collection::isEmpty)
                    .getElse(() -> false);

            if (!isEmpty) {
                runnableIfNotEmpty.run(obj);
                return true;
            }
        }
        return false;
    }
*/

    public static <T> boolean doIfCast(@Nullable Object obj, @NonNull Class<T> clazz, @NonNull ObjRunnable<T> runnableIfCast) {
        if (ClassUtils.isInstanceOf(obj, clazz)) {
            runnableIfCast.run(ObjectUtils.castOrThrow(obj));
            return true;
        }
        return false;
    }

    public static <T> boolean doIfCast(@Nullable Object obj, @NonNull Class<T> clazz,
                                       @NonNull ObjRunnable<T> runnableIfCast, @Nullable Runnable runnableIfNotCast) {
        if (doIfCast(obj, clazz, runnableIfCast)) {
            return true;
        }
        doIfExists(runnableIfNotCast, Runnable::run);
        return false;
    }

    public static void doSafe(@NonNull UnsafeRunnable runnable) {
        try {
            runnable.run();
        } catch (Throwable e) {
            Log.e(TAG, e);
        }
    }

    public static boolean doSyncTask(@NonNull AtomicBoolean holder, @NonNull Runnable runnable) {
        if (holder.compareAndSet(false, true)) {
            try {
                runInCurrentThread(runnable);
                return true;
            } finally {
                holder.set(false);
            }
        }
        return false;
    }

    @Nullable
    public static <T> T getSafe(@NonNull Callable<T> callable) {
        return getSafe(callable, null);
    }

    @Nullable
    public static <T> T getSafe(@NonNull Callable<T> callable, @Nullable T defValue) {
        try {
            return callable.call();
        } catch (Throwable e) {
            Log.e(TAG, e);
        }
        return defValue;
    }

    @Nullable
    public static <T, V> V getIfExists(@Nullable T obj, @NonNull ObjCallable<T, V> callableIfExists) {
        if (obj != null) {
            return callableIfExists.call(obj);
        }
        return null;
    }

    public static <T, V> V getIfExists(@Nullable T obj, @NonNull ObjCallable<T, V> callableIfExists, @Nullable V resultIfNotExists) {
        if (obj != null) {
            return callableIfExists.call(obj);
        }
        return resultIfNotExists;
    }

    public static <T> T createIfNotExists(@Nullable T obj, @NonNull Callable<T> callableIfNotExists) {
        if (obj == null) {
            return getSafe(callableIfNotExists);
        }
        return obj;
    }

/*
    public static <T, V> V getIfNotEmpty(@Nullable T obj, @NonNull ObjCallable<T, V> callableIfNotEmpty) {
        if (obj != null) {
            Boolean isEmpty = from(obj, Boolean.class)
                    .ifCast(String.class, String::isEmpty)
                    .ifCast(Collection.class, Collection::isEmpty)
                    .getElse(() -> Boolean.FALSE);

            if (!isEmpty) {
                return callableIfNotEmpty.call(obj);
            }
        }
        return null;
    }
*/


    @Nullable
    public static <T> T getIfCast(@Nullable Object obj, @NonNull Class<T> clazz) {
        return getIfCast(obj, clazz, obj1 -> obj1, null);
    }

    @Nullable
    public static <T,V> V getIfCast(@Nullable Object obj, @NonNull Class<T> clazz, @NonNull ObjCallable<T,V> callableIfExists) {
        return getIfCast(obj, clazz, callableIfExists, null);
    }

    public static <T,V> V getIfCast(@Nullable Object obj, @NonNull Class<T> clazz, @NonNull ObjCallable<T,V> callableIfExists, @Nullable V resultIfNotCast) {
        if (ClassUtils.isInstanceOf(obj, clazz)) {
            return callableIfExists.call(ObjectUtils.castOrThrow(obj));
        }
        return resultIfNotCast;
    }

    @NonNull
    public static <V> V getNonNull(@Nullable V obj, @NonNull V defValue) {
        return obj == null ? defValue : obj;
    }

    @NonNull
    public static <V> V getNonNull(@Nullable V obj, @NonNull ValueCallable<V> callableIfNull) {
        return obj == null ? callableIfNull.call() : obj;
    }

    public static void trace(@NonNull String TAG, @NonNull Object msg, @NonNull Runnable task) {
        long start = SystemClock.uptimeMillis();
        task.run();
        long delta = SystemClock.uptimeMillis() - start;
        Log.i(TAG, "TRACE: ", msg, " (", delta, "ms)");
    }

    public static <T> T trace(@NonNull String TAG, @NonNull Object msg, @NonNull Callable<T> task) {
        long start = SystemClock.uptimeMillis();
        try {
            return task.call();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        } finally {
            long delta = SystemClock.uptimeMillis() - start;
            Log.i(TAG, "TRACE: ", msg, " (", delta, "ms)");
        }
    }

    public static void dumpCurrentStack(@NonNull String message, boolean onlyLog) {
        if (Log.isEnabledLog()) {
            Exception e = new IllegalThreadStateException(message);
            Log.w(TAG, e.getMessage(), e);
            if (!onlyLog) {
                throw new IllegalStateException(e);
            }
        }
    }

    public static void failInUIThread(boolean onlyLog) {
        if (isUIThread()) {
            dumpCurrentStack("Executing in UI thread", onlyLog);
        }
    }

    public static void failInBackground(boolean onlyLog) {
        if (!isUIThread()) {
            dumpCurrentStack("Executing in background", onlyLog);
        }
    }


}

