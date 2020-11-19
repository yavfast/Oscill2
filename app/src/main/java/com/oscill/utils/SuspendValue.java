package com.oscill.utils;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.executor.ObjRunnable;
import com.oscill.utils.executor.ValueCallable;

public class SuspendValue<V> {

    private volatile V value;
    private final ValueCallable<V> callable;
    private volatile boolean suspended = true;

    public SuspendValue(@NonNull ValueCallable<V> callable) {
        this.callable = callable;
    }

    public final V get() {
        if (suspended) {
            synchronized (this) {
                if (suspended) {
                    value = callable.call();
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
