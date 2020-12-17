package com.oscill.types;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.executor.ObjRunnable;
import com.oscill.utils.executor.UnsafeCallable;

public class SuspendValue<V> {

    private volatile V value;
    private final UnsafeCallable<V> callable;
    private volatile boolean suspended = true;

    public SuspendValue(@NonNull UnsafeCallable<V> callable) {
        this.callable = callable;
    }

    public final V get() {
        try {
            return getOrThrow();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    public final V getOrThrow() throws Exception {
        if (suspended) {
            synchronized (this) {
                if (suspended) {
                    value = callable.unsafeCall();
                    suspended = false;
                }
            }
        }

        return value;
    }

    public void set(V value) {
        synchronized (this) {
            this.value = value;
            suspended = false;
        }
    }

    public boolean hasValue() {
        synchronized (this) {
            return !suspended && value != null;
        }
    }

    public void reset() {
        reset(null);
    }

    public void reset(@Nullable ObjRunnable<V> onReset) {
        if (!suspended) {
            synchronized (this) {
                if (!suspended) {
                    if (onReset != null && value != null) {
                        onReset.run(value);
                    }
                    suspended = true;
                }
            }
        }
    }

}
