package com.oscill.utils.executor;

import androidx.annotation.NonNull;

public interface ObjCallable2<T1, T2, V> {
    V call(@NonNull T1 obj1, @NonNull T2 obj2);
}
