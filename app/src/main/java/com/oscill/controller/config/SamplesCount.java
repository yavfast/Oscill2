package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.Oscill;
import com.oscill.controller.OscillProperty;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;

public class SamplesCount extends OscillProperty<Integer> {

    private static final int DEF_DIV_COUNT = 8;
    private static final int DEF_SAMPLES_BY_DIV_COUNT = 32;

    private final ChannelSWMode channelSWMode;

    private int divCount = DEF_DIV_COUNT;
    private int samplesByDivCount = DEF_SAMPLES_BY_DIV_COUNT;

    public SamplesCount(@NonNull Oscill oscill, @NonNull ChannelSWMode channelSWMode) {
        super(oscill);

        this.channelSWMode = channelSWMode;
        channelSWMode.addLinkedSetting(this);
    }

    public int getDivCount() {
        return divCount;
    }

    public int getSamplesByDivCount() {
        return samplesByDivCount;
    }

    @NonNull
    public ChannelSWMode getChannelSWMode() {
        return channelSWMode;
    }

    @NonNull
    @Override
    protected Unit requestRealValueUnit() {
        return new Unit(Dimension.NORMAL, Unit.COUNT);
    }

    @NonNull
    @Override
    protected Range<Integer> requestNativePropertyRange() throws Exception {
        int min = 1;
        int max = getOscill().getMaxSamplesDataSize();
        return new Range<>(min, max);
    }

    @NonNull
    @Override
    protected Integer requestNativeValue() throws Exception {
        return getOscill().getSamplesDataSize();
    }

    @Override
    protected Integer applyNativeValue(@NonNull Integer nativeValue) throws Exception {
        return getOscill().setSamplesDataSize(nativeValue);
    }

    private int getSampleSize() {
        switch (getChannelSWMode().getSWMode()) {
            case AVG_HIRES:
            case PEAK_1:
            case PEAK_2:
                return 2;

            case NORMAL:
            case AVG:
            default:
                return 1;
        }
    }

    @Override
    protected Integer realToNative(@NonNull Integer realValue) {
        return realValue * getSampleSize();
    }

    @Override
    protected Integer nativeToReal(@NonNull Integer nativeValue) {
        return nativeValue / getSampleSize();
    }

    public void setSamplesCount(int divCount, int samplesByDivCount) throws Exception {
        this.divCount = divCount;
        this.samplesByDivCount = samplesByDivCount;
        setRealValue(getDivCount() * getSamplesByDivCount());
    }

    public int getSamplesCount() {
        return getRealValue();
    }

}
