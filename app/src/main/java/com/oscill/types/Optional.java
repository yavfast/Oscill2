package com.oscill.types;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.utils.ObjectUtils;
import com.oscill.utils.StringUtils;
import com.oscill.utils.executor.Executor;
import com.oscill.utils.executor.ObjRunnable;

import java.util.NoSuchElementException;

public class Optional<T> {

    private static final Optional<?> EMPTY = new Optional<>();
    private static final Optional<?> LOADING = new Optional<>();

    private final T value;

    private final SuspendValue<String> hashValue = new SuspendValue<>(this::calcHashValue);

    private final Throwable error;

    private Optional() {
        this.value = null;
        this.error = null;
    }

    @NonNull
    public static<T> Optional<T> empty() {
        @SuppressWarnings("unchecked")
        Optional<T> t = (Optional<T>) EMPTY;
        return t;
    }

    @NonNull
    public static<T> Optional<T> loading() {
        @SuppressWarnings("unchecked")
        Optional<T> t = (Optional<T>) LOADING;
        return t;
    }

    @NonNull
    public static <T> Optional<T> of(@NonNull T value) {
        return new Optional<>(value);
    }

    @NonNull
    public static <T> Optional<T> ofNullable(@Nullable T value) {
        return value == null ? empty() : of(value);
    }

    @NonNull
    public static <T> Optional<T> error(@NonNull Throwable e) {
        return new Optional<>(e);
    }

    public Optional(@NonNull T value) {
        this.value = value;
        this.error = null;
    }

    protected Optional(@NonNull Throwable e) {
        this.value = null;
        this.error = e;
    }

    @NonNull
    public String calcHashValue() {
        return toString();
    }

    @NonNull
    public String getHashValue() {
        return hashValue.get();
    }

    @NonNull
    public T get() {
        if (value == null) {
            throw new NoSuchElementException("No value present");
        }
        return value;
    }

    @NonNull
    public T orElse(@NonNull T other) {
        return value != null ? value : other;
    }

    @Nullable
    public T orNull() {
        return value;
    }

    public boolean isPresent() {
        return value != null;
    }

    public boolean isEmpty() {
        return value == null;
    }

    public boolean isLoading() {
        return this == LOADING;
    }

    @NonNull
    public Optional<T> doIfPresent(@NonNull ObjRunnable<T> runnable) {
        Executor.doIfExists(value, runnable);
        return this;
    }

    @NonNull
    public Optional<T> doIfEmpty(@NonNull Runnable runnable) {
        if (isEmpty()) {
            runnable.run();
        }
        return this;
    }

    @NonNull
    public Optional<T> doIfLoading(@NonNull Runnable runnable) {
        if (isLoading()) {
            runnable.run();
        }
        return this;
    }

    @NonNull
    public Optional<T> doIfError(@NonNull ObjRunnable<Throwable> runnable) {
        Executor.doIfExists(error, runnable);
        return this;
    }

    @Override
    public boolean equals(@Nullable Object obj) {
        return ObjectUtils.equals(this, obj, (obj1, obj2) ->
                obj1.value == obj2.value || StringUtils.equals(obj1.getHashValue(), obj2.getHashValue())
        );
    }

    @NonNull
    @Override
    public String toString() {
        return String.valueOf(value);
    }

    @Override
    public int hashCode() {
        return getHashValue().hashCode();
    }
}
