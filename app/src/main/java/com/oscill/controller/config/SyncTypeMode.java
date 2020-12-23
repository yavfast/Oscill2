package com.oscill.controller.config;

import androidx.annotation.NonNull;

import com.oscill.controller.BaseOscillMode;
import com.oscill.controller.Oscill;
import com.oscill.types.BitSet;

public class SyncTypeMode extends BaseOscillMode {

    public SyncTypeMode(@NonNull Oscill oscill) {
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

    public enum SyncType {
        AUTO            (BitSet.fromBits(0, 0)),
        WAIT_TIMEOUT    (BitSet.fromBits(0, 1)),
        FREE            (BitSet.fromBits(1, 0)),
        WAIT            (BitSet.fromBits(1, 1));

        private final BitSet bitSet;

        SyncType(@NonNull BitSet bitSet) {
            this.bitSet = bitSet;
        }

        @NonNull
        BitSet getBitSet() {
            return bitSet;
        }
    }

    public void setSyncType(@NonNull SyncType mode) throws Exception {
        apply(mode.getBitSet());
    }

    @NonNull
    public SyncType getSyncType() {
        BitSet mode = getMode();
        for (SyncType syncType : SyncType.values()) {
            if (syncType.getBitSet().equals(mode)) {
                return syncType;
            }
        }
        return SyncType.AUTO;
    }

}
