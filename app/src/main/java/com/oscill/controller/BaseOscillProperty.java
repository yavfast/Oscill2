package com.oscill.controller;

import androidx.annotation.CallSuper;
import androidx.annotation.NonNull;

import com.oscill.types.Range;
import com.oscill.types.SuspendValue;
import com.oscill.types.Unit;
import com.oscill.utils.Log;
import com.oscill.utils.ObjectUtils;

public abstract class BaseOscillProperty<T,V> extends BaseOscillSetting {

    protected BaseOscillProperty(@NonNull Oscill oscill) {
        super(oscill);
    }

    private final SuspendValue<T> nativeValue = new SuspendValue<>(this::requestNativeValue);
    private final SuspendValue<V> realValue = new SuspendValue<>(this::requestRealValue);
    private final SuspendValue<Unit> realValueUnit = new SuspendValue<>(this::requestRealValueUnit);

    private final SuspendValue<Range<T>> nativeRange = new SuspendValue<>(this::requestNativePropertyRange);
    private final SuspendValue<Range<V>> realRange = new SuspendValue<>(() -> {
        Range<T> nativeRange = getNativeRange();
        return new Range<>(nativeToReal(nativeRange.getLower()), nativeToReal(nativeRange.getUpper()));
    });

    @Override
    protected void onReset() {
        nativeValue.reset();
        realValue.reset();

        nativeRange.reset();
        realRange.reset();
    }

    @NonNull
    protected abstract Unit requestRealValueUnit();
    @NonNull
    protected abstract Range<T> requestNativePropertyRange() throws Exception;
    protected abstract T applyNativeValue(@NonNull T nativeValue) throws Exception;

    @NonNull
    protected T requestNativeValue() throws Exception {
        throw new IllegalStateException("Need set data");
    }

    @NonNull
    private V requestRealValue() throws Exception {
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

    protected void setRealValue(@NonNull V value) throws Exception {
        if (!this.realValue.hasValue() || !ObjectUtils.equals(this.realValue.get(), value)) {
            this.realValue.set(value);
            setNativeValue(realToNative(value));
            onRealValueChanged(this.realValue.get()); // realValue maybe changed
        }
    }

    @NonNull
    private T checkNativeRange(@NonNull T value) throws Exception {
        Comparable<T> comparable = (Comparable<T>)value;
        Range<T> nativeRange = getNativeRange();
        if (comparable.compareTo(nativeRange.getLower()) < 0) {
            Log.w(TAG, "Out of range: ", nativeRange, "; value: ", value);
            return nativeRange.getLower();
        }
        if (comparable.compareTo(nativeRange.getUpper()) > 0) {
            Log.w(TAG, "Out of range: ", nativeRange, "; value: ", value);
            return nativeRange.getUpper();
        }
        return value;
    }

    public void setNativeValue(@NonNull T value) throws Exception {
        value = checkNativeRange(value);

        boolean hasValue = this.nativeValue.hasValue();
        if (!hasValue || !ObjectUtils.equals(this.nativeValue.get(), value)) {
            T nativeValue = applyNativeValue(value);
            this.nativeValue.set(nativeValue);
            onNativeValueChanged(nativeValue);
        }
    }

    @CallSuper
    protected void onNativeValueChanged(@NonNull T value) {
        this.realValue.reset();
        resetLinkedSettings();
    }

    protected void onRealValueChanged(@NonNull V value) {

    }

}
