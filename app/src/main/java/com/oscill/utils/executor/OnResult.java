package com.oscill.utils.executor;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.types.Optional;

public interface OnResult<T> {

    void run(@NonNull Optional<T> result);

    default void of(@Nullable T value) {
        run(value != null ? Optional.of(value) : Optional.empty());
    }

    default void from(@NonNull UnsafeCallable<T> value) {
        try {
            of(value.call());
        } catch (Throwable e) {
            error(e);
        }
    }

    default void empty() {
        run(Optional.empty());
    }

    default void error(@NonNull Throwable e) {
        run(Optional.error(e));
    }

    /**
     * Simple implementation
     */
    @NonNull
    static <V> OnResult<V> doIfPresent(@NonNull ObjRunnable<V> runnable) {
        return result -> result.doIfPresent(runnable);
    }

}
