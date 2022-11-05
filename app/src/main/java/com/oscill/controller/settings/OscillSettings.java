package com.oscill.controller.settings;

import androidx.annotation.Keep;

@Keep
public class OscillSettings {

    @Keep
    public static class ProcessingTypeMode {
        public String processingType;
        public String dataOutputType;
        public String bufferType;
    }

    @Keep
    public static class ChannelSettings {
        public String sensitivity;
        public String offset;
        public String syncMode;
        public String hwMode;
        public String swMode;
        public String syncLevel;
    }

    public ProcessingTypeMode processingTypeMode;
    public ChannelSettings channelSettings;

    public String cpuTickLength;
    public String samplingPeriod;
    public String samplesCount;
    public String samplesOffset;

    public String syncTypeMode;
}
