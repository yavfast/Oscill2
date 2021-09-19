package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChanelHWMode;
import com.oscill.controller.config.ChanelOffset;
import com.oscill.controller.config.ChanelSWMode;
import com.oscill.controller.config.ChannelSensitivity;
import com.oscill.controller.config.ChanelSyncLevel;
import com.oscill.controller.config.ChanelSyncMode;
import com.oscill.controller.config.CpuTickLength;
import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.config.SamplesOffset;
import com.oscill.controller.config.SamplingPeriod;
import com.oscill.controller.config.SamplesCount;
import com.oscill.controller.config.SyncTypeMode;
import com.oscill.types.Dimension;
import com.oscill.utils.executor.OnResult;

import java.io.IOException;

public class OscillConfig extends BaseOscillSetting {

    private final ChannelSensitivity channelSensitivity;
    private final ChanelOffset chanelOffset;
    private final ChanelSyncMode chanelSyncMode;
    private final ChanelHWMode chanelHWMode;
    private final ChanelSWMode chanelSWMode;
    private final ChanelSyncLevel chanelSyncLevel;

    private final CpuTickLength cpuTickLength;
    private final SamplingPeriod samplingPeriod;
    private final SamplesCount samplesCount;
    private final SamplesOffset samplesOffset;

    private final SyncTypeMode syncTypeMode;
    private final ProcessingTypeMode processingTypeMode;

    public OscillConfig(@NonNull Oscill oscill) {
        super(oscill);

        this.channelSensitivity = new ChannelSensitivity(oscill);
        this.chanelOffset = new ChanelOffset(oscill, channelSensitivity);
        this.chanelSyncMode = new ChanelSyncMode(oscill);
        this.chanelHWMode = new ChanelHWMode(oscill);
        this.chanelSWMode = new ChanelSWMode(oscill);
        this.chanelSyncLevel = new ChanelSyncLevel(oscill, channelSensitivity);

        this.syncTypeMode = new SyncTypeMode(oscill);
        this.processingTypeMode = new ProcessingTypeMode(oscill);

        this.cpuTickLength = new CpuTickLength(oscill);
        this.samplesCount = new SamplesCount(oscill, chanelSWMode);
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
    public ChanelOffset getChanelOffset() {
        return chanelOffset;
    }

    @NonNull
    public ChanelSyncMode getChanelSyncMode() {
        return chanelSyncMode;
    }

    @NonNull
    public ChanelHWMode getChanelHWMode() {
        return chanelHWMode;
    }

    @NonNull
    public ChanelSWMode getChanelSWMode() {
        return chanelSWMode;
    }

    @NonNull
    public ChanelSyncLevel getChanelSyncLevel() {
        return chanelSyncLevel;
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
            int responseTimeout = (int) getSamplingPeriod().getDivTime(Dimension.MILLI);
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
