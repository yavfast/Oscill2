package com.oscill.utils.executor;

import androidx.annotation.NonNull;

public interface ObjRunnable<T> {
    void run(@NonNull T obj);
}
