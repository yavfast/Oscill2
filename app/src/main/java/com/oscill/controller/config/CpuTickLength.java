package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

public class CpuTickLength extends OscillProperty<Integer> {

    public CpuTickLength(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected Unit requestRealValueUnit() {
        return new Unit(Dimension.PICO, Unit.SECOND);
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        int min = getOscill().getCPUTickMinLength();
        int max = 65500;
        return new Range<>(min, max);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getCPUTickLength();
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setCPUTickLength(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Integer realValue) {
        return realValue / 10;
    }

    @Override
    protected Integer nativeToReal(@NonNull Integer nativeValue) {
        return nativeValue * 10;
    }

    public void setCPUFreq(int cpuFreq, @NonNull Dimension dimension) throws Exception {
        float tickLength = Dimension.NORMAL.toDimension(1f, Dimension.PICO).floatValue() / dimension.toDimension(cpuFreq, Dimension.NORMAL).floatValue();
        setRealValue(Math.round(tickLength));
    }

}
