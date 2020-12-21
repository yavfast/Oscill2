package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import static com.oscill.types.Dimension.PICO;

public class RealtimeSamplingPeriod extends OscillProperty<Long> {

    private final CpuTickLength cpuTickLength;

    public RealtimeSamplingPeriod(@NonNull Oscill oscill, @NonNull CpuTickLength cpuTickLength) {
        super(oscill);
        this.cpuTickLength = cpuTickLength;
    }

    @NonNull
    public CpuTickLength getCpuTickLength() {
        return cpuTickLength;
    }

    @NonNull
    @Override
    protected Unit requestRealValueUnit() {
        return new Unit(PICO, Unit.SECOND);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getSamplingPeriod();
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        int min = getOscill().getSamplingMinPeriod();
        int max = 167000;
        return new Range<>(min, max);
    }

    @Override
    protected Integer onNativeValueChanged(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setSamplingPeriod(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Long realValue) {
        return Math.round(((float)realValue) / (float)getCpuTickLength().getRealValue()) * 256;
    }

    @Override
    protected Long nativeToReal(@NonNull Integer nativeValue) {
        return ((long) (nativeValue / 256)) * getCpuTickLength().getRealValue();
    }

    public void setSamplingPeriod(float divTime, @NonNull Dimension timeDim, int samplingCountByDiv) throws Exception {
        float samplingTime = timeDim.toDimension(divTime / (float) samplingCountByDiv, PICO);
        setRealValue((long)samplingTime);
    }

    public float getDivTime(@NonNull Dimension timeDim, int samplingCountByDiv) {
        return PICO.toDimension(getRealValue() * samplingCountByDiv, timeDim);
    }

    public float getSampleTime(@NonNull Dimension timeDim) {
        return PICO.toDimension(getRealValue(), timeDim);
    }

}
