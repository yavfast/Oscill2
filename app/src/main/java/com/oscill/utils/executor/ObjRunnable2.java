package com.oscill.utils.executor;

import androidx.annotation.NonNull;

public interface ObjRunnable2<T1, T2> {
    void run(@NonNull T1 obj1, @NonNull T2 obj2);
}
