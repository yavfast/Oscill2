package com.oscill.utils.executor;

import androidx.annotation.NonNull;

public interface UnsafeObjRunnable<T> {
    void run(@NonNull T obj) throws Exception;
}
