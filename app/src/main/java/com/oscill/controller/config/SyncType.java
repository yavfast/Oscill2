package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class SyncType extends BaseOscillMode {

    public SyncType(@NonNull Oscill oscill) {
        super(oscill);
    }

    @NonNull
    @Override
    protected BitSet requestMode() throws Exception {
        return getOscill().getSyncType();
    }

    @NonNull
    @Override
    protected BitSet onModeChanged(@NonNull BitSet bitSet) throws Exception {
        return getOscill().setSyncType(bitSet);
    }

    /**
     * Имя регистра: RT - Тип запуска
     * Формат регистра: 1 байт, побитный
     * Описание регистра: 	бит 10 :	------00  – автоматический запуск (после TA)
     * 				                    ------01  – ждущий запуск (лимит TW)
     * 				                    ------10  – свободный запуск
     * 				                    ------11  – бесконечно ждущий запуск
     * Регистр зависит от: нет
     * От регистра зависят: использование регистра TA или TW
     * Примечание: свободный и бесконечно ждущий запуски поддерживаются начиная с встроенного ПО (firmware) версии 1.25.
     */

    public enum SyncTypeMode {
        AUTO, WAIT_TIMEOUT, FREE, WAIT
    }

    public void setSyncTypeMode(@NonNull SyncTypeMode mode) throws Exception {
        BitSet modeBitSet = null;
        switch (mode) {
            case AUTO:
                modeBitSet = BitSet.fromBits(0, 0);
                break;
            case WAIT_TIMEOUT:
                modeBitSet = BitSet.fromBits(0, 1);
                break;
            case FREE:
                modeBitSet = BitSet.fromBits(1, 0);
                break;
            case WAIT:
                modeBitSet = BitSet.fromBits(1, 1);
                break;
        }

        apply(modeBitSet);
    }

}
