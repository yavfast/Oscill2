package com.oscill.controller;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.oscill.controller.config.ChannelSWMode;
import com.oscill.controller.config.ChannelSensitivity;
import com.oscill.types.BitSet;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.utils.ArrayUtils;
import com.oscill.utils.DataUtils;
import com.oscill.utils.Log;

import java.util.ArrayList;

import math.fft.ComplexArray;
import math.fft.Fourier;

public class OscillData {

    private static final String TAG = Log.getTag(OscillData.class);

    private static final int DATA_HEADER_SIZE = 4;

    private final byte[] data;

    private float tStep;
    private float tOffset;

    private float vStep;
    private float vMin;
    private float vMax;
    private float vOffset;
    private float vTrigger;

    private BitSet dataInfo;
    private BitSet chanelInfo;
    private ChannelSWMode.SWMode swMode;

    private int[] iData;
    private float[] tData;
    private float[] vData;
    private float[] vData2;
    private ComplexArray fft;

    private int iDataMin;
    private int iDataMax;
    private int iDataAvg;

    private float vDataMin;
    private float vDataMax;
    private float vDataAvg;

    private float tDataFreq;

    public OscillData(@NonNull OscillConfig config, @NonNull byte[] data) {
        this.data = data;
        prepareDataInfo(config);
    }

    /**
     *  2 байта - атрибуты оцифровки (описание развертки и синхронизации)
     * Затем для каждого из каналов:
     *   2 байта - атрибуты канала (формат массива выборок этого канала);
     *   2 байта - размер массива выборок канала (в байтах);  TODO: Уже нет этого размера
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
//        this.vStep = channelSensitivity.getSensitivityStep(Dimension.MILLI);

        this.vOffset = config.getChannelOffset().getRealValue();
        this.vTrigger = config.getChannelSyncLevel().getRealValue() + this.vOffset;

        Range<Float> vRange = channelSensitivity.getSensitivityRange(Dimension.MILLI);
        this.vMax = vRange.getUpper() + vOffset;
        this.vMin = vRange.getLower() + vOffset;

        float vRealRange = this.vMax - this.vMin;
        int vRes = (getSwMode() == ChannelSWMode.SWMode.AVG_HIRES) ? 0xffff : 0xff;
        this.vStep = vRealRange / (vRes + 1);
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

        prepareAdvVoltData();
        calcFreq();

//        getFFT();
    }

    private static final Fourier fourier = new Fourier();

    @NonNull
    public ComplexArray getFFT() {
        if (fft == null) {
            float[] data = getVoltData();
            synchronized (fourier) {
                fft = fourier.forwardDFT(new ComplexArray(data));
//                fft = new ComplexArray(data).naiveForwardDFT();
            }
        }
        return fft;
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

    private void prepareAdvVoltData() {
        int[] iData = this.iData;
        if (iData == null || iData.length == 0) {
            return;
        }

        int iDataMin = Integer.MAX_VALUE;
        int iDataMax = Integer.MIN_VALUE;
        int iDataSum = 0;

        for (int i = 0, iDataLength = iData.length; i < iDataLength; i++) {
            int iValue = iData[i];

            iDataSum += iValue;

            if (iValue > iDataMax) {
                iDataMax = iValue;
            } else if (iValue < iDataMin) {
                iDataMin = iValue;
            }
        }

        this.iDataMin = iDataMin;
        this.iDataMax = iDataMax;
        this.iDataAvg = iDataSum / iData.length;

        this.vDataMax = toVData(iDataMax);
        this.vDataMin = toVData(iDataMin);
        this.vDataAvg = toVData(this.iDataAvg);
    }

    private float toVData(int iData) {
        return vMin + iData * vStep;
    }

    private void calcFreq() {
        this.tDataFreq = 0f;

        int[] iData = this.iData;
        if (iData == null || iData.length == 0) {
            return;
        }

        int iDataAvg = this.iDataAvg;
        ArrayList<Integer> posSegments = new ArrayList<>(32);
        ArrayList<Integer> negSegments = new ArrayList<>(32);

        boolean currSegmentSign = true;
        int currSegmentLen = 0;

        for (int i = 0, iDataLength = iData.length; i < iDataLength; i++) {
            int iValue = iData[i];

            boolean sign = iValue - iDataAvg > 0;
            if (currSegmentSign == sign) {
                currSegmentLen++;
            } else {
                if (currSegmentLen > 0) {
                    ArrayList<Integer> currSegments = currSegmentSign ? posSegments : negSegments;
                    currSegments.add(currSegmentLen);
                }

                currSegmentSign = sign;
                currSegmentLen = 0;
            }
        }

        if (ArrayUtils.isNotEmpty(posSegments) && ArrayUtils.isNotEmpty(negSegments)) {
            int segmentsCount = posSegments.size() + negSegments.size();
            int avgSegment = iData.length / segmentsCount;

            posSegments = ArrayUtils.filteredArray(posSegments, item -> item >= avgSegment);
            negSegments = ArrayUtils.filteredArray(negSegments, item -> item >= avgSegment);
            if (segmentsCount < 3) {
                return;
            }

            int avgPosSegment = calcAvg(posSegments, avgSegment);
            int avgNegSegment = calcAvg(negSegments, avgSegment);
            float tPeriod = (avgPosSegment + avgNegSegment) * this.tStep;
            this.tDataFreq = 1000f / tPeriod;
        }
    }

    private static int calcAvg(@NonNull ArrayList<Integer> arrayList, int defValue) {
        int arrayListSize = arrayList.size();
        if (arrayListSize == 0) {
            return defValue;
        }

        int sum = 0;
        for (int i = 0; i < arrayListSize; i++) {
            sum += arrayList.get(i);
        }
        return sum / arrayListSize;
    }

    @NonNull
    private float[] prepareSimpleData() {
        int[] data = getIntData();
        float vStep = getVStep();
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
        float vStep = getVStep();
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
        float vStep = getVStep();
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

    public float getVStep() {
        return vStep;
    }

    public float getTriggerV() {
        return vTrigger;
    }

    public float getVDataMin() {
        return vDataMin;
    }

    public float getVDataMax() {
        return vDataMax;
    }

    public float getVDataAvg() {
        return vDataAvg;
    }

    public float getDataFreq() {
        return tDataFreq;
    }
}
