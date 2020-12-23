package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

import static com.oscill.types.Dimension.PICO;

public class SamplesOffset extends OscillProperty<Long> {

    private final SamplingPeriod samplingPeriod;
    private final SamplesCount samplesCount;

    public SamplesOffset(@NonNull Oscill oscill,
                         @NonNull SamplingPeriod samplingPeriod,
                         @NonNull SamplesCount samplesCount) {
        super(oscill);

        this.samplingPeriod = samplingPeriod;
        samplingPeriod.addLinkedSetting(this);

        this.samplesCount = samplesCount;
        samplesCount.addLinkedSetting(this);
    }

    @NonNull
    private SamplesCount getSamplesCount() {
        return samplesCount;
    }

    @NonNull
    public SamplingPeriod getSamplingPeriod() {
        return samplingPeriod;
    }

    @NonNull
    @Override
    protected Unit requestRealValueUnit() {
        return new Unit(PICO, Unit.SECOND);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getSamplesOffset();
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        return new Range<>(0, getSamplesCount().getSamplesCount());
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setSamplesOffset(nativeValue);
    }

    @Override
    protected Integer realToNative(@NonNull Long realValue) {
        return (int)((float)realValue / getSamplingPeriod().getSampleTime(PICO));
    }

    @Override
    protected Long nativeToReal(@NonNull Integer nativeValue) {
        return (long)(nativeValue * getSamplingPeriod().getSampleTime(PICO));
    }

    public void setOffset(float time, @NonNull Dimension dimension) throws Exception {
        long realValue = (long)dimension.toDimension(time, PICO);
        setRealValue(realValue);
    }

    public float getOffset(@NonNull Dimension dimension) {
        return PICO.toDimension(getRealValue(), dimension);
    }
}
