package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChannelHWMode;
import com.oscill.controller.config.ChannelOffset;
import com.oscill.controller.config.ChannelSWMode;
import com.oscill.controller.config.ChannelSensitivity;
import com.oscill.controller.config.ChannelSyncLevel;
import com.oscill.controller.config.ChannelSyncMode;
import com.oscill.controller.config.CpuTickLength;
import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.config.SamplesCount;
import com.oscill.controller.config.SamplesOffset;
import com.oscill.controller.config.SamplingPeriod;
import com.oscill.controller.config.SyncTypeMode;
import com.oscill.types.Dimension;
import com.oscill.utils.executor.OnResult;

import java.io.IOException;

public class OscillConfig extends BaseOscillSetting {

    private final ChannelSensitivity channelSensitivity;
    private final ChannelOffset channelOffset;
    private final ChannelSyncMode channelSyncMode;
    private final ChannelHWMode channelHWMode;
    private final ChannelSWMode channelSWMode;
    private final ChannelSyncLevel channelSyncLevel;

    private final CpuTickLength cpuTickLength;
    private final SamplingPeriod samplingPeriod;
    private final SamplesCount samplesCount;
    private final SamplesOffset samplesOffset;

    private final SyncTypeMode syncTypeMode;
    private final ProcessingTypeMode processingTypeMode;

    public OscillConfig(@NonNull Oscill oscill) {
        super(oscill);

        this.channelSensitivity = new ChannelSensitivity(oscill);
        this.channelOffset = new ChannelOffset(oscill, channelSensitivity);
        this.channelSyncMode = new ChannelSyncMode(oscill);
        this.channelHWMode = new ChannelHWMode(oscill);
        this.channelSWMode = new ChannelSWMode(oscill);
        this.channelSyncLevel = new ChannelSyncLevel(oscill, channelSensitivity);

        this.syncTypeMode = new SyncTypeMode(oscill);
        this.processingTypeMode = new ProcessingTypeMode(oscill);

        this.cpuTickLength = new CpuTickLength(oscill);
        this.samplesCount = new SamplesCount(oscill, channelSWMode);
        this.samplingPeriod = new SamplingPeriod(oscill, cpuTickLength, samplesCount);
        this.samplesOffset = new SamplesOffset(oscill, samplingPeriod, samplesCount);
    }

    @Override
    protected void onReset() {
        // TODO:
    }

    @NonNull
    public ChannelSensitivity getChannelSensitivity() {
        return channelSensitivity;
    }

    @NonNull
    public ChannelOffset getChannelOffset() {
        return channelOffset;
    }

    @NonNull
    public ChannelSyncMode getChannelSyncMode() {
        return channelSyncMode;
    }

    @NonNull
    public ChannelHWMode getChannelHWMode() {
        return channelHWMode;
    }

    @NonNull
    public ChannelSWMode getChannelSWMode() {
        return channelSWMode;
    }

    @NonNull
    public ChannelSyncLevel getChannelSyncLevel() {
        return channelSyncLevel;
    }

    @NonNull
    public CpuTickLength getCpuTickLength() {
        return cpuTickLength;
    }

    @NonNull
    public SamplingPeriod getSamplingPeriod() {
        return samplingPeriod;
    }

    @NonNull
    public SamplesCount getSamplesCount() {
        return samplesCount;
    }

    @NonNull
    public SamplesOffset getSamplesOffset() {
        return samplesOffset;
    }

    @NonNull
    public SyncTypeMode getSyncTypeMode() {
        return syncTypeMode;
    }

    @NonNull
    public ProcessingTypeMode getProcessingTypeMode() {
        return processingTypeMode;
    }

    public void requestData(@NonNull OnResult<OscillData> onResult) {
        try {
            int responseTimeout = (int) getSamplingPeriod().getRequestTime(Dimension.MILLI);
            byte[] data = getOscill().getData(responseTimeout);
            if (data.length > 4) {
                OscillData oscillData = new OscillData(this, data);
                onResult.of(oscillData);
            } else {
                onResult.empty();
            }
        } catch (IOException e) {
            onResult.error(e);
        }
    }
}
