package com.oscill.utils.executor.runnable;

import androidx.annotation.NonNull;

public interface IRunnableOnView<T> {
    void run(@NonNull T view);
}
