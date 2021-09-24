package com.oscill.controller;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.controller.config.ChannelSWMode;
import com.oscill.controller.config.ChannelSensitivity;
import com.oscill.types.BitSet;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.utils.DataUtils;
import com.oscill.utils.Log;

public class OscillData {

    private static final String TAG = Log.getTag(OscillData.class);

    private static final int DATA_HEADER_SIZE = 6;

    private final byte[] data;

    private float tStep;
    private float tOffset;

    private float vStep;
    private float vMin;
    private float vMax;
    private float vOffset;

    private BitSet dataInfo;
    private BitSet chanelInfo;
    private ChannelSWMode.SWMode swMode;

    private int[] iData;
    private float[] tData;
    private float[] vData;
    private float[] vData2;

    public OscillData(@NonNull OscillConfig config, @NonNull byte[] data) {
        this.data = data;
        prepareDataInfo(config);
    }

    /**
     *  2 байта - атрибуты оцифровки (описание развертки и синхронизации)
     * Затем для каждого из каналов:
     *   2 байта - атрибуты канала (формат массива выборок этого канала);
     *   2 байта - размер массива выборок канала (в байтах);
     *   XX байт - массив выборок канала.
     *
     * Первый байт атрибутов оцифровки
     * Бит 0.  Использованный способ оцифровки:
     * 	0 - однократная (realtime),
     * 	1 - стробоскопическая (эквивалентная, RIS)
     * Бит 1.   Параллельность оцифровки и передачи в Comp:
     * 	0 - передаваемые массивы уже полностью оцифрованы
     * 	1 – массив передается в процессе оцифровки
     * Бит 2.  Бесконечность оцифровки
     * 	0 – массив выборок имеет конечный размер
     * 	1 – выборки будут передаваться бесконечно  (до остановки со стороны comp-а)
     * Биты 54 Источник запуска оцифровки
     * 	00– таймаут (в режиме автоматического запуска по истечению регистра TA)
     * 	01 – запуск произошел по условию синхронизации - спаду сигнала
     * 	10 – запуск произошел по условию синхронизации - фронту сигнала
     * Биты 76  - количество каналов:
     * 	00 – один канал
     * 	01 – два канала
     * 	10 – три канала
     * 	11 – четыре канала
     *
     * Первый байт атрибутов канала
     * Биты 210.  Формат выборок
     * 000   –  усреднение  (один байт на выборку)
     * 001   - режим высокого разрешения: два байта на одну выборку
     * 010   – пиковый режим: один байт (мин или макс) на выборку (interlaced)
     * 011   – пиковый режим: два байта (мин и макс) на одну выборку
     * 100   – выборка АЦП соотв. выборке вых.массива (один байт на выборку)
     */
    private void prepareDataInfo(@NonNull OscillConfig config) {
        this.tStep = config.getSamplingPeriod().getSampleTime(Dimension.MILLI);
        this.tOffset = config.getSamplesOffset().getOffset(Dimension.MILLI);

        ChannelSensitivity channelSensitivity = config.getChannelSensitivity();
        this.vStep = channelSensitivity.getSensitivityStep(Dimension.MILLI);

        this.vOffset = config.getChannelOffset().getRealValue();

        Range<Float> vRange = channelSensitivity.getSensitivityRange(Dimension.MILLI);
        this.vMax = vRange.getUpper() + vOffset;
        this.vMin = vRange.getLower() + vOffset;
    }

    @NonNull
    public BitSet getDataInfo() {
        if (dataInfo == null) {
            dataInfo = BitSet.fromBytes(data[0]);
        }
        return dataInfo;
    }

    @NonNull
    public BitSet getChanelInfo() {
        if (chanelInfo == null) {
            chanelInfo = BitSet.fromBytes(data[2]);
        }
        return chanelInfo;
    }

    @NonNull
    public ChannelSWMode.SWMode getSwMode() {
        if (swMode == null) {
            swMode = ChannelSWMode.SWMode.getSWMode(getChanelInfo());
        }
        return swMode;
    }

    public int getDataSize() {
        return (data.length - DATA_HEADER_SIZE) / getSwMode().getSampleSize();
    }

    @NonNull
    public int[] getIntData() {
        if (iData == null) {
            switch (getSwMode().getSampleDataSize()) {
                case 1:
                    iData = DataUtils.getIntData1Byte(data, DATA_HEADER_SIZE);
                    break;
                case 2:
                    iData = DataUtils.getIntData2Byte(data, DATA_HEADER_SIZE);
                    break;
                default:
                    throw new IllegalArgumentException("Sample size");
            }
        }
        return iData;
    }

    @NonNull
    public float[] getTimeData() {
        if (tData == null) {
            int dataSize = getDataSize();
            float[] tData = new float[dataSize];
            float tStep = this.tStep;
            float tOffset = this.tOffset;
            for (int idx = 0; idx < dataSize; idx++) {
                tData[idx] = (tStep * idx) - tOffset;
            }
            this.tData = tData;
        }
        return tData;
    }

    void prepareData() {
        getTimeData();
        getVoltData();
    }

    @NonNull
    public float[] getVoltData() {
        if (vData == null) {
            switch (getSwMode()) {
                case NORMAL:
                case AVG:
                case PEAK_1:
                    vData = prepareSimpleData();
                    break;

                case AVG_HIRES:
                    vData = prepareAvgHiResData();
                    break;

                case PEAK_2:
                    vData = preparePeak2Data();
                    break;
            }
        }
        return vData;
    }

    @Nullable
    public float[] getVoltData2() {
        return vData2;
    }


    @NonNull
    private float[] prepareSimpleData() {
        int[] data = getIntData();
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xff;
        float vMin = getMinV();

        int dataSize = getDataSize();
        float[] vData = new float[dataSize];

        int idx = 0;
        while (idx < dataSize) {
            vData[idx] = vMin + (data[idx] * vStep);
            idx++;
        }

        return vData;
    }

    @NonNull
    private float[] prepareAvgHiResData() {
        int[] data = getIntData();
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xffff;
        float vMin = getMinV();

        int dataSize = getDataSize();
        float[] vData = new float[dataSize];

        int idx = 0;
        while (idx < dataSize) {
            vData[idx] = vMin + (data[idx] * vStep);
            idx++;
        }

        return vData;
    }

    @NonNull
    private float[] preparePeak2Data() {
        int dataSize = getDataSize();
        float[] vDataMin = new float[dataSize];
        float[] vDataMax = new float[dataSize];

        int[] data = getIntData();
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xff;
        float vMin = getMinV();

        int idx = 0;
        int dataIdx = 0;
        while (idx < dataSize) {
            vDataMin[idx] = vMin + (data[dataIdx++] * vStep);
            vDataMax[idx] = vMin + (data[dataIdx++] * vStep);

            idx++;
        }

        this.vData2 = vDataMax;
        return vDataMin;
    }

    public float getMaxV() {
        return vMax;
    }

    public float getMinV() {
        return vMin;
    }

}
