package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.types.Range;
import com.oscill.utils.SuspendValue;

public abstract class BaseOscillProperty<T,V> {

    private T nativeValue;
    private V realValue;

    private final SuspendValue<Range<T>> nativeRange = new SuspendValue<>(this::requestNativePropertyRange);
    private final SuspendValue<Range<V>> realRange = new SuspendValue<>(() -> {
        Range<T> nativeRange = getNativeRange();
        return new Range<>(nativeToReal(nativeRange.getLower()), nativeToReal(nativeRange.getUpper()));
    });

    @NonNull
    protected abstract Range<T> requestNativePropertyRange() throws Exception;
    protected abstract T onNativeValueChanged(@NonNull T nativeValue) throws Exception;

    protected abstract T realToNative(@NonNull V realValue);
    protected abstract V nativeToReal(@NonNull T nativeValue);

    public V getRealValue() {
        return realValue;
    }

    public T getNativeValue() {
        return nativeValue;
    }

    @NonNull
    public Range<T> getNativeRange() throws Exception {
        return nativeRange.getOrThrow();
    }

    @NonNull
    public Range<V> getRealRange() throws Exception {
        return realRange.getOrThrow();
    }

    public void setRealValue(@NonNull V value) throws Exception {
        if (this.realValue != value) {
            this.realValue = value;
            setNativeValue(realToNative(value));
            onRealValueChanged(this.realValue);
        }
    }

    public void setNativeValue(@NonNull T value) throws Exception {
        if (this.nativeValue != value) {
            this.nativeValue = onNativeValueChanged(value);
            this.realValue = nativeToReal(this.nativeValue);
        }
    }

    protected void onRealValueChanged(@NonNull V value) {

    }

}
