package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class ChannelSWMode extends BaseOscillMode {

    public ChannelSWMode(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected BitSet requestMode() throws Exception {
        return getOscill().getChanelSWMode();
    }

    @NonNull
    @Override
    protected BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception {
        return getOscill().setChanelSWMode(bitSet);
    }

    /**
     * Имя регистра: M1 - Программный режим канала (обработка выборок)
     * Формат регистра: 1 байт
     * Описание регистра: Биты 210:
     * -----000   – усреднение с отбрасыванием младших разрядов (1байт/выборка)
     * -----001   – усреднение  с повышением разрешения  (2 байта/выборка)
     * -----010   – пиковый режим – поочередно (2байта/2выборки)
     * -----011   – пиковый режим – повыборочно (2байта/выборка)
     * -----100   – обычный режим: байт массива = выборка АЦП (1байт/выборка)
     * Данный регистр относится к обработке, осуществляемой в Oscill-е. Кроме неё (или в дополнение к ней) аналогичная обработка может
     * осуществляться Comp-ом на основании нескольких подряд массивов выборок, полученных от Oscill.
     *  Количество проходов усреднения/накопления определяется регистром A1. При медленных развертках усреднение/накопление пиковых
     *  значений производится даже в течение одного прохода.
     * Регистр зависит от: RS (режимы невозможны при стробоскопической и параллельной оцифровках),
     * TS (режимы невозможны при малых периодах дискретизации)
     * От регистра зависят: количество выборок QS и QSh
     */

    public enum SWMode {
        NORMAL      (BitSet.fromBits(1, 0, 0)),
        AVG         (BitSet.fromBits(0, 0, 0)),
        AVG_HIRES   (BitSet.fromBits(0, 0, 1)),
        PEAK_1      (BitSet.fromBits(0, 1, 0)),
        PEAK_2      (BitSet.fromBits(0, 1, 1));

        private final BitSet bitSet;

        SWMode(@NonNull BitSet bitSet) {
            this.bitSet = bitSet;
        }

        @NonNull
        BitSet getBitSet() {
            return bitSet;
        }

        public int getSampleSize() {
            switch (this) {
                case AVG_HIRES:
                case PEAK_2:
                    return 2;

                default:
                    return 1;
            }
        }

        public int getSampleDataSize() {
            switch (this) {
                case AVG_HIRES:
                    return 2;

                default:
                    return 1;
            }
        }

        @NonNull
        public static SWMode getSWMode(@NonNull BitSet mode) {
            for (SWMode swMode : SWMode.values()) {
                if (swMode.getBitSet().equals(mode)) {
                    return swMode;
                }
            }
            return SWMode.NORMAL;
        }
    }

    public void setSWMode(@NonNull SWMode mode) throws Exception {
        apply(mode.getBitSet());
    }

    @NonNull
    public SWMode getSWMode() {
        BitSet mode = getMode();
        return SWMode.getSWMode(mode);
    }
}
