package com.oscill.controller;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.types.Range;
import com.oscill.types.Unit;
import com.oscill.types.SuspendValue;

public abstract class BaseOscillProperty<T,V> {

    private final Oscill oscill;

    public BaseOscillProperty(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
    }

    @NonNull
    public Oscill getOscill() {
        return oscill;
    }

    private final SuspendValue<T> nativeValue = new SuspendValue<>(this::requestNativeValue);
    private final SuspendValue<V> realValue = new SuspendValue<>(this::requestRealValue);
    private final SuspendValue<Unit> realValueUnit = new SuspendValue<>(this::requestRealValueUnit);


    private final SuspendValue<Range<T>> nativeRange = new SuspendValue<>(this::requestNativePropertyRange);
    private final SuspendValue<Range<V>> realRange = new SuspendValue<>(() -> {
        Range<T> nativeRange = getNativeRange();
        return new Range<>(nativeToReal(nativeRange.getLower()), nativeToReal(nativeRange.getUpper()));
    });

    @NonNull
    protected abstract Unit requestRealValueUnit();
    @NonNull
    protected abstract Range<T> requestNativePropertyRange() throws Exception;
    protected abstract T onNativeValueChanged(@NonNull T nativeValue) throws Exception;

    @NonNull
    protected T requestNativeValue() throws Exception {
        throw new IllegalStateException("Need set data");
    }

    @NonNull
    protected V requestRealValue() throws Exception {
        return nativeToReal(getNativeValue());
    }

    protected abstract T realToNative(@NonNull V realValue);
    protected abstract V nativeToReal(@NonNull T nativeValue);

    public V getRealValue() {
        return realValue.get();
    }

    @NonNull
    public Unit getRealValueUnit() {
        return realValueUnit.get();
    }

    public T getNativeValue() {
        return nativeValue.get();
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
        if (!this.realValue.hasValue() || this.realValue.get() != value) {
            this.realValue.set(value);
            setNativeValue(realToNative(value));
            onRealValueChanged(this.realValue.get()); // realValue maybe changed
        }
    }

    public void setNativeValue(@NonNull T value) throws Exception {
        if (!this.nativeValue.hasValue() || this.nativeValue.get() != value) {
            T nativeValue = onNativeValueChanged(value);
            this.nativeValue.set(nativeValue);
            this.realValue.set(nativeToReal(nativeValue));
        }
    }

    protected void onRealValueChanged(@NonNull V value) {

    }

}
