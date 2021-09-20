package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChanelSWMode;
import com.oscill.controller.config.ChannelSensitivity;
import com.oscill.types.BitSet;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.utils.Log;

public class OscillData {

    private static final String TAG = Log.getTag(OscillData.class);

    private static final int DATA_HEADER_SIZE = 6;

    private final OscillConfig config;
    public final byte[] data;

    private float tStep;
    private float tOffset;

    private float vStep;
    private float vMin;
    private float vMax;

    private float vOffset;

    public int dataSize;
    private BitSet dataInfo;
    private BitSet chanelInfo;
    private ChanelSWMode.SWMode swMode;

    public float[] tData;
    public float[] vData;
    public float[] vData2;

    public OscillData(@NonNull OscillConfig config, @NonNull byte[] data) {
        this.config = config;
        this.data = data;
        prepareDataInfo();
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
    private void prepareDataInfo() {
        this.tStep = config.getSamplingPeriod().getSampleTime(Dimension.MILLI);
        this.tOffset = config.getSamplesOffset().getOffset(Dimension.MILLI);

        ChannelSensitivity channelSensitivity = config.getChannelSensitivity();
        this.vStep = channelSensitivity.getSensitivityStep(Dimension.MILLI);

        this.vOffset = config.getChanelOffset().getRealValue();

        Range<Float> vRange = channelSensitivity.getSensitivityRange(Dimension.MILLI);
        this.vMax = vRange.getUpper() + vOffset;
        this.vMin = vRange.getLower() + vOffset;

        dataInfo = BitSet.fromBytes(data[0]);
        chanelInfo = BitSet.fromBytes(data[2]);
        swMode = ChanelSWMode.SWMode.getSWMode(chanelInfo);

        dataSize = (data.length - DATA_HEADER_SIZE) / swMode.getDataSize();

        // TODO:
//        int headerDataSize = Oscill.bytesToInt(new byte[]{data[4], data[5]});
//        if (headerDataSize != dataSize) {
//            Log.w(TAG, "Wrong data size: ", dataSize, "; expected: ", headerDataSize);
//        }
    }

    public void prepareData() {
        switch (swMode) {
            case NORMAL:
            case AVG:
            case PEAK_1:
                prepareSimpleData();
                break;

            case AVG_HIRES:
                prepareAvgHiResData();
                break;

            case PEAK_2:
                preparePeak2Data();
                break;
        }
    }

    private void prepareSimpleData() {
        float[] tData = new float[dataSize];
        float[] vData = new float[dataSize];

        byte[] data = this.data;
        int dataSize = this.dataSize;
        float tStep = this.tStep;
        float tOffset = this.tOffset;
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xff;
        float vMin = getMinV();

        int idx = 0;
        int dataIdx = DATA_HEADER_SIZE;
        while (idx < dataSize) {
            tData[idx] = (tStep * idx) - tOffset;
            vData[idx] = vMin + (data[dataIdx++] & 0xff) * vStep;

            idx++;
        }

        this.tData = tData;
        this.vData = vData;
    }

    private void prepareAvgHiResData() {
        float[] tData = new float[dataSize];
        float[] vData = new float[dataSize];

        byte[] data = this.data;
        int dataSize = this.dataSize;
        float tStep = this.tStep;
        float tOffset = this.tOffset;
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xffff;
        float vMin = getMinV();

        int value;
        int idx = 0;
        int dataIdx = DATA_HEADER_SIZE;
        while (idx < dataSize) {
            tData[idx] = (tStep * idx) - tOffset;
            value = ((data[dataIdx++] & 0xff) << 8) | (data[dataIdx++] & 0xff);
            vData[idx] = vMin + value * vStep;

            idx++;
        }

        this.tData = tData;
        this.vData = vData;
    }

    private void preparePeak2Data() {
        float[] tData = new float[dataSize];
        float[] vDataMin = new float[dataSize];
        float[] vDataMax = new float[dataSize];

        byte[] data = this.data;
        int dataSize = this.dataSize;
        float tStep = this.tStep;
        float tOffset = this.tOffset;
        float vStep = Math.abs(getMaxV() - getMinV()) / (float) 0xff;
        float vMin = getMinV();

        int idx = 0;
        int dataIdx = DATA_HEADER_SIZE;
        while (idx < dataSize) {
            tData[idx] = (tStep * idx) - tOffset;
            vDataMin[idx] = vMin + (data[dataIdx++] & 0xff) * vStep;
            vDataMax[idx] = vMin + (data[dataIdx++] & 0xff) * vStep;

            idx++;
        }

        this.tData = tData;
        this.vData = vDataMin;
        this.vData2 = vDataMax;
    }

    public float getMaxV() {
        return vMax;
    }

    public float getMinV() {
        return vMin;
    }

}
