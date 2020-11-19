package com.oscill.utils.executor;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.Log;

import java.util.concurrent.ExecutionException;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

public class AsyncTask<V> implements IAsyncTask {

    private static final String TAG = "AsyncTask";

    private final ScheduledFuture<V> task;

    AsyncTask(@NonNull ScheduledFuture<V> task) {
        this.task = task;
    }

    @Nullable
    public V getOrThrow() throws ExecutionException {
        try {
            return task.get();
        } catch (InterruptedException ignored) {
        }
        return null;
    }

    @Nullable
    public V getOrThrow(long timeout) throws ExecutionException {
        try {
            return task.get(timeout, TimeUnit.MILLISECONDS);
        } catch (InterruptedException | TimeoutException ignored) {
        }
        return null;
    }

    @Nullable
    public V get() {
        try {
            return task.get();
        } catch (InterruptedException ignored) {
        } catch (ExecutionException e) {
            Log.e(TAG, e);
        }
        return null;
    }

    @Nullable
    public V get(long timeout) {
        try {
            return task.get(timeout, TimeUnit.MILLISECONDS);
        } catch (InterruptedException ignored) {
        } catch (ExecutionException | TimeoutException e) {
            Log.e(TAG, e);
        }
        return null;
    }

    @Override
    public void await() {
        get();
    }
}
