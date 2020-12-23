package com.oscill.controller;

import androidx.annotation.NonNull;

import com.oscill.controller.config.ChanelSensitivity;
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
    private float vStep;
    private float vMin;
    private float vMax;

    private float vOffset;

    public int dataSize;
    private BitSet dataInfo;
    private BitSet chanelInfo;

    public float[] tData;
    public float[] vData;

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
     * 100   –  усреднение  (один байт на выборку)
     * 001   - режим высокого разрешения: два байта на одну выборку
     * 010   – пиковый режим: один байт (мин или макс) на выборку (interlaced)
     * 011   – пиковый режим: два байта (мин и макс) на одну выборку
     * 100   – выборка АЦП соотв. выборке вых.массива (один байт на выборку)
     */
    private void prepareDataInfo() {
        this.tStep = config.getSamplingPeriod().getSampleTime(Dimension.MILLI);

        ChanelSensitivity chanelSensitivity = config.getChanelSensitivity();
        this.vStep = chanelSensitivity.getSensitivityStep(Dimension.MILLI);

        this.vOffset = config.getChanelOffset().getRealValue();

        Range<Float> vRange = chanelSensitivity.getSensitivityRange(Dimension.MILLI);
        this.vMax = vRange.getUpper() + vOffset;
        this.vMin = vRange.getLower() + vOffset;

        dataInfo = BitSet.fromBytes(data[0]);
        chanelInfo = BitSet.fromBytes(data[2]);

        dataSize = data.length - DATA_HEADER_SIZE;

        // TODO:
//        int headerDataSize = Oscill.bytesToInt(new byte[]{data[4], data[5]});
//        if (headerDataSize != dataSize) {
//            Log.w(TAG, "Wrong data size: ", dataSize, "; expected: ", headerDataSize);
//        }
    }

    public void prepareData() {
        float[] tData = new float[dataSize];
        float[] vData = new float[dataSize];

        byte[] data = this.data;
        int dataSize = this.dataSize;
        float tStep = this.tStep;
        float vStep = this.vStep;

        int idx = 0;
        int dataIdx = DATA_HEADER_SIZE;
        while (idx < dataSize) {
            tData[idx] = tStep * idx;
            vData[idx] = byteToInt(data[dataIdx]) * vStep;

            idx++;
            dataIdx++;
        }

        this.tData = tData;
        this.vData = vData;
    }

    private static int byteToInt(byte value) {
        return (value >= 0 ? value : value & 0xFF) - 0x80;
    }

    public float getMaxV() {
        return vMax;
    }

    public float getMinV() {
        return vMin;
    }

}
