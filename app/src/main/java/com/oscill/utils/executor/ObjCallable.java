package com.oscill.utils.executor;

import androidx.annotation.NonNull;

public interface ObjCallable<T, V> {
    V call(@NonNull T obj);
}
