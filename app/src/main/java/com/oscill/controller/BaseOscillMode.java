package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.types.BitSet;
import com.oscill.types.SuspendValue;
import com.oscill.utils.ObjectUtils;

public abstract class BaseOscillMode {

    private final Oscill oscill;
    private final SuspendValue<BitSet> mode = new SuspendValue<>(this::requestMode);

    public BaseOscillMode(@NonNull Oscill oscill) {
        super();
        this.oscill = oscill;
    }

    @NonNull
    public Oscill getOscill() {
        return oscill;
    }

    @NonNull
    public BitSet getMode() {
        return mode.get().copy();
    }

    @NonNull
    protected abstract BitSet requestMode() throws Exception;

    @NonNull
    protected abstract BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception;

    protected void apply(@NonNull BitSet bitSet) throws Exception {
        if (mode.hasValue() && ObjectUtils.equals(mode.get(), bitSet)) {
            return;
        }
        mode.set(onModeChanged(bitSet));
    }

}
