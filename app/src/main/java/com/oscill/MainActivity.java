package com.oscill;

import android.graphics.Color;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.github.mikephil.charting.charts.LineChart;
import com.github.mikephil.charting.components.XAxis;
import com.github.mikephil.charting.components.YAxis;
import com.github.mikephil.charting.data.Entry;
import com.github.mikephil.charting.data.LineData;
import com.github.mikephil.charting.data.LineDataSet;
import com.github.mikephil.charting.interfaces.datasets.ILineDataSet;
import com.oscill.controller.Oscill;
import com.oscill.controller.OscillData;
import com.oscill.controller.OscillManager;
import com.oscill.controller.config.ChannelHWMode;
import com.oscill.controller.config.ChannelOffset;
import com.oscill.controller.config.ChannelSWMode;
import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.config.SamplesOffset;
import com.oscill.controller.config.SamplingTime;
import com.oscill.controller.config.Sensitivity;
import com.oscill.controller.config.SyncTypeMode;
import com.oscill.events.OnOscillConfigChanged;
import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.ArrayListEx;
import com.oscill.types.Dimension;
import com.oscill.types.Range;
import com.oscill.types.Unit;
import com.oscill.types.UnitFormatter;
import com.oscill.utils.Log;
import com.oscill.utils.StringUtils;
import com.oscill.utils.ViewUtils;
import com.oscill.utils.executor.EventHolder;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends AppCompatActivity {

    private final static String TAG = Log.getTag(MainActivity.class);

    LineChart chart;

    TextView activeText;
    TextView activeStateText;
    Button runBtn;
    Button singleRunBtn;

    TextView normBtn;
    TextView peakBtn;
    TextView avgBtn;
    TextView avgHiResBtn;

    TextView dcBtn;
    TextView acBtn;

    TextView highFilterBtn;
    TextView lowFilterBtn;

    TextView triggerAutoBtn;
    TextView triggerTimeoutBtn;
    TextView triggerWaitBtn;
    TextView triggerFreeBtn;
    TextView triggerFrontBtn;
    TextView triggerBackBtn;
    TextView triggerUpBtn;
    TextView triggerDownBtn;

    TextView voltAutoBtn;
    TextView voltUpBtn;
    TextView voltDownBtn;
    TextView voltDivText;
    TextView voltZeroOffsetBtn;
    TextView voltOffsetUpBtn;
    TextView voltOffsetDownBtn;

    TextView timeAutoBtn;
    TextView timeUpBtn;
    TextView timeDownBtn;
    TextView timeDivText;
    TextView timeZeroOffsetBtn;
    TextView timeOffsetUpBtn;
    TextView timeOffsetDownBtn;

    TextView vMinText;
    TextView vMaxText;
    TextView vAvgText;

    private final EventHolder<?> onOscillConnected = EventsController.onReceiveEvent(this, OnOscillConnected.class, event ->
            onOscillConnected()
    );

    private final EventHolder<?> onOscillConfigChanged = EventsController.onReceiveEvent(this, OnOscillConfigChanged.class, event ->
            onOscillConfigChanged()
    );

    private final EventHolder<?> onOscillData = EventsController.onReceiveEventAsync(this, OnOscillData.class, event ->
            prepareData(event.oscillData)
    );

    private final EventHolder<?> onOscillError = EventsController.onReceiveEvent(this, OnOscillError.class, event ->
            onOscillError(event.getError())
    );

    private final AtomicBoolean updateChart = new AtomicBoolean(true);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);

        activeText = findViewById(R.id.activeText);
        activeStateText = findViewById(R.id.activeStateText);

        runBtn = findViewById(R.id.runBtn);
        runBtn.setOnClickListener(v -> doStartStop());

        singleRunBtn = findViewById(R.id.singleRunBtn);
        singleRunBtn.setOnClickListener(v -> doSingleStart());

        normBtn = findViewById(R.id.normBtn);
        normBtn.setOnClickListener(v ->
            setChannelSWMode(ChannelSWMode.SWMode.NORMAL)
        );
        peakBtn = findViewById(R.id.peakBtn);
        peakBtn.setOnClickListener(v ->
            setChannelSWMode(ChannelSWMode.SWMode.PEAK_1)
        );
        avgBtn = findViewById(R.id.avgBtn);
        avgBtn.setOnClickListener(v ->
            setChannelSWMode(ChannelSWMode.SWMode.AVG)
        );
        avgHiResBtn = findViewById(R.id.avgHiResBtn);
        avgHiResBtn.setOnClickListener(v ->
            setChannelSWMode(ChannelSWMode.SWMode.AVG_HIRES)
        );

        dcBtn = findViewById(R.id.dcBtn);
        dcBtn.setOnClickListener(v ->
            setChannelHWModeACDC(false)
        );
        acBtn = findViewById(R.id.acBtn);
        acBtn.setOnClickListener(v ->
            setChannelHWModeACDC(true)
        );

        highFilterBtn = findViewById(R.id.highFilterBtn);
        highFilterBtn.setOnClickListener(v ->
            changeChannelHWModeFilters(true, false)
        );
        lowFilterBtn = findViewById(R.id.lowFilterBtn);
        lowFilterBtn.setOnClickListener(v ->
            changeChannelHWModeFilters(false, true)
        );

        triggerAutoBtn = findViewById(R.id.triggerAutoBtn);
        triggerAutoBtn.setOnClickListener(v ->
            doSetTriggerType(SyncTypeMode.SyncType.AUTO)
        );
        triggerTimeoutBtn = findViewById(R.id.triggerTimeoutBtn);
        triggerTimeoutBtn.setOnClickListener(v ->
                doSetTriggerType(SyncTypeMode.SyncType.WAIT_TIMEOUT)
        );
        triggerWaitBtn = findViewById(R.id.triggerWaitBtn);
        triggerWaitBtn.setOnClickListener(v ->
                doSetTriggerType(SyncTypeMode.SyncType.WAIT)
        );
        triggerFreeBtn = findViewById(R.id.triggerFreeBtn);
        triggerFreeBtn.setOnClickListener(v ->
                doSetTriggerType(SyncTypeMode.SyncType.FREE)
        );
        triggerFrontBtn = findViewById(R.id.triggerFrontBtn);
        triggerFrontBtn.setOnClickListener(v ->
            doChangeTriggerFront()
        );
        triggerBackBtn = findViewById(R.id.triggerBackBtn);
        triggerBackBtn.setOnClickListener(v ->
            doChangeTriggerBack()
        );
        triggerUpBtn = findViewById(R.id.triggerUpBtn);
        triggerUpBtn.setOnClickListener(v ->
            doChangeTriggerLevel(+8)
        );
        triggerDownBtn = findViewById(R.id.triggerDownBtn);
        triggerDownBtn.setOnClickListener(v ->
            doChangeTriggerLevel(-8)
        );

        voltAutoBtn = findViewById(R.id.voltAutoBtn);
        voltAutoBtn.setOnClickListener(v ->
            doAutoVoltByDiv()
        );

        voltUpBtn = findViewById(R.id.voltUpBtn);
        voltUpBtn.setOnClickListener(v ->
            doChangeVoltByDiv(+1)
        );
        voltDownBtn = findViewById(R.id.voltDownBtn);
        voltDownBtn.setOnClickListener(v ->
            doChangeVoltByDiv(-1)
        );
        voltDivText = findViewById(R.id.voltDivText);

        voltZeroOffsetBtn = findViewById(R.id.voltZeroOffsetBtn);
        voltZeroOffsetBtn.setOnClickListener(v ->
                doChangeVoltOffset(0)
        );
        voltOffsetUpBtn = findViewById(R.id.voltOffsetUpBtn);
        voltOffsetUpBtn.setOnClickListener(v ->
                doChangeVoltOffset(+1)
        );
        voltOffsetDownBtn = findViewById(R.id.voltOffsetDownBtn);
        voltOffsetDownBtn.setOnClickListener(v ->
                doChangeVoltOffset(-1)
        );

        timeAutoBtn = findViewById(R.id.timeAutoBtn);
        timeAutoBtn.setOnClickListener(v ->
            doAutoTimeByDiv()
        );
        timeUpBtn = findViewById(R.id.timeUpBtn);
        timeUpBtn.setOnClickListener(v ->
            doChangeTimeByDiv(+1)
        );
        timeDownBtn = findViewById(R.id.timeDownBtn);
        timeDownBtn.setOnClickListener(v ->
            doChangeTimeByDiv(-1)
        );
        timeDivText = findViewById(R.id.timeDivText);

        timeZeroOffsetBtn = findViewById(R.id.timeZeroOffsetBtn);
        timeZeroOffsetBtn.setOnClickListener(v ->
                doChangeTimeOffset(0)
        );
        timeOffsetUpBtn = findViewById(R.id.timeOffsetUpBtn);
        timeOffsetUpBtn.setOnClickListener(v ->
                doChangeTimeOffset(+1)
        );
        timeOffsetDownBtn = findViewById(R.id.timeOffsetDownBtn);
        timeOffsetDownBtn.setOnClickListener(v ->
                doChangeTimeOffset(-1)
        );

        vMinText = findViewById(R.id.vMinText);
        vMaxText = findViewById(R.id.vMaxText);
        vAvgText = findViewById(R.id.vAvgText);

        initChart();

        EventsController.resumeEvents(onOscillConnected, onOscillConfigChanged, onOscillData, onOscillError);
        connectToDevice();
    }

    private void onOscillConfigChanged() {
        updateChart.set(true);
    }

    private void updateSettings() {
        runOnActivity(() -> {
            updateActivityButtons();
            updateSWModeButtons();
            updateACDCButtons();
            updateChannelFiltersButtons();
            updateTrigger();
            updateVoltByDiv();
            updateTimeByDiv();
        });
    }

    private void doSetTriggerType(@NonNull SyncTypeMode.SyncType syncType) {
        OscillManager.runConfigTask(oscillConfig -> {
            oscillConfig.getSyncTypeMode().setSyncType(syncType);

            updateTrigger();
        });
    }

    private void doChangeTriggerFront() {
        OscillManager.runConfigTask(oscillConfig -> {
            boolean hasSyncByFront = oscillConfig.getChannelSyncMode().hasSyncByFront();
            oscillConfig.getChannelSyncMode()
                    .setSyncByFront(!hasSyncByFront)
                    .setHistFront(!hasSyncByFront);

            updateTrigger();
        });
    }

    private void doChangeTriggerBack() {
        OscillManager.runConfigTask(oscillConfig -> {
            boolean hasSyncByBack = oscillConfig.getChannelSyncMode().hasSyncByBack();
            oscillConfig.getChannelSyncMode()
                    .setSyncByBack(!hasSyncByBack)
                    .setHistBack(!hasSyncByBack);

            updateTrigger();
        });
    }

    private void doChangeTriggerLevel(int delta) {
        OscillManager.runConfigTask(oscillConfig -> {
            int syncLevel = oscillConfig.getChannelSyncLevel().getNativeValue();
            oscillConfig.getChannelSyncLevel().setNativeValue(syncLevel + delta);
        });
    }

    private void doAutoVoltByDiv() {

    }

    private void doChangeVoltByDiv(int step) {
        OscillManager.runConfigTask(oscillConfig -> {
            Sensitivity curSensitivity = oscillConfig.getChannelSensitivity().getSensitivity();
            Sensitivity newSensitivity = curSensitivity.getNext(step);

            oscillConfig.getChannelSensitivity().setSensitivity(newSensitivity);

            updateVoltByDiv();
        });
    }

    private void doChangeVoltOffset(int step) {
        OscillManager.runConfigTask(oscillConfig -> {
            ChannelOffset channelOffset = oscillConfig.getChannelOffset();
            if (step == 0) {
                Range<Integer> range = channelOffset.getNativeRange();
                channelOffset.setNativeValue((range.getLower() + range.getUpper()) / 2);
            } else {
                channelOffset.setNativeValue(channelOffset.getNativeValue() + step * 32);
            }

            updateVoltByDiv();
        });
    }

    private void doAutoTimeByDiv() {

    }

    private void doChangeTimeByDiv(int step) {
        OscillManager.runConfigTask(oscillConfig -> {
            SamplingTime curSamplingTime = oscillConfig.getSamplingPeriod().getSamplingPeriod();
            SamplingTime newSamplingTime = curSamplingTime.getNext(step);

            oscillConfig.getSamplingPeriod().setSamplingPeriod(newSamplingTime);

            updateTimeByDiv();
        });
    }

    private void updateTimeByDiv() {
        OscillManager.runConfigTask(oscillConfig -> {
            SamplingTime curSamplingTime = oscillConfig.getSamplingPeriod().getSamplingPeriod();
            updateTimeByDiv(curSamplingTime);
        });
    }

    private void updateTimeByDiv(@NonNull SamplingTime samplingTime) {
        runOnActivity(() ->
                timeDivText.setText(
                        StringUtils.concat(String.valueOf(samplingTime.getValue()), " ", samplingTime.getDimension().getPrefix(), "s"))
        );
    }

    private void doChangeTimeOffset(int step) {
        OscillManager.runConfigTask(oscillConfig -> {
            SamplesOffset samplesOffset = oscillConfig.getSamplesOffset();
            if (step == 0) {
                samplesOffset.setNativeValue(0);
            } else {
                samplesOffset.setNativeValue(samplesOffset.getNativeValue() + step * oscillConfig.getSamplesCount().getSamplesByDivCount());
            }
        });
    }

    private void updateTrigger() {
        OscillManager.runConfigTask(oscillConfig -> {
            SyncTypeMode.SyncType syncType = oscillConfig.getSyncTypeMode().getSyncType();
            boolean syncFront = oscillConfig.getChannelSyncMode().hasSyncByFront();
            boolean syncBack = oscillConfig.getChannelSyncMode().hasSyncByBack();
            Integer syncLevel = oscillConfig.getChannelSyncLevel().getNativeValue();

            updateTrigger(syncType, syncFront, syncBack, syncLevel);
        });
    }

    private void updateTrigger(@NonNull SyncTypeMode.SyncType syncType, boolean syncFront, boolean syncBack, @NonNull Integer syncLevel) {
        runOnActivity(() -> {
            ViewUtils.setTextBold(triggerAutoBtn, syncType == SyncTypeMode.SyncType.AUTO);
            ViewUtils.setTextBold(triggerTimeoutBtn, syncType == SyncTypeMode.SyncType.WAIT_TIMEOUT);
            ViewUtils.setTextBold(triggerWaitBtn, syncType == SyncTypeMode.SyncType.WAIT);
            ViewUtils.setTextBold(triggerFreeBtn, syncType == SyncTypeMode.SyncType.FREE);

            ViewUtils.setTextBold(triggerFrontBtn, syncFront);
            ViewUtils.setTextBold(triggerBackBtn, syncBack);

        });
    }

    private void updateVoltByDiv() {
        OscillManager.runConfigTask(oscillConfig -> {
            Sensitivity curSensitivity = oscillConfig.getChannelSensitivity().getSensitivity();
            updateVoltByDiv(curSensitivity);
        });
    }

    private void updateVoltByDiv(@NonNull Sensitivity sensitivity) {
        runOnActivity(() ->
                voltDivText.setText(
                        StringUtils.concat(String.valueOf(sensitivity.getValue()), " ", sensitivity.getDimension().getPrefix(), "V"))
        );
    }

    @Override
    protected void onResume() {
        super.onResume();
        EventsController.resumeEvents(onOscillConnected, onOscillConfigChanged, onOscillData, onOscillError);
    }

    @Override
    protected void onPause() {
        EventsController.pauseEvents(onOscillConnected, onOscillConfigChanged, onOscillData, onOscillError);
        OscillManager.pause();
        super.onPause();
    }

    private void doStartStop() {
        Executor.runInSyncQueue(() -> {
            try {
                if (!OscillManager.isConnected()) {
                    OscillManager.init();
                    return;
                }

                if (!OscillManager.isActive()) {
                    OscillManager.start();
                    return;
                }

                OscillManager.pause();
            } finally {
                updateActivityButtons();
            }
        });
    }

    private void runOnActivity(@NonNull Runnable runnable) {
        Executor.runInUIThread(this, activity -> runnable.run());
    }

    private void updateActivityButtons() {
        runOnActivity(() -> {
            if (!OscillManager.isConnected()) {
                activeStateText.setText(R.string.disconnected);
            } else {
                activeStateText.setText(R.string.connected);
            }

            if (OscillManager.isActive()) {
                runBtn.setText(R.string.stop);
            } else {
                runBtn.setText(R.string.run);
            }
        });
    }

    private void doSingleStart() {
        if (OscillManager.isConnected() && !OscillManager.isActive()) {
            OscillManager.requestNextData();
        }
    }

    private void changeChannelHWModeFilters(boolean hiFilter, boolean loFilter) {
        OscillManager.runConfigTask(oscillConfig -> {
            ChannelHWMode channelHWMode = oscillConfig.getChannelHWMode();
            if (hiFilter) {
                channelHWMode.setFilter3MHz(!channelHWMode.isFilter3MHzEnabled());
            }
            if (loFilter) {
                channelHWMode.setFilter3kHz(!channelHWMode.isFilter3kHzEnabled());
            }

            updateChannelFiltersButtons();
        });
    }

    private void updateChannelFiltersButtons() {
        OscillManager.runConfigTask(oscillConfig ->
            updateChannelFiltersButtons(oscillConfig.getChannelHWMode().isFilter3MHzEnabled(), oscillConfig.getChannelHWMode().isFilter3kHzEnabled())
        );
    }

    private void updateChannelFiltersButtons(boolean hiFilter, boolean loFilter) {
        runOnActivity(() -> {
            ViewUtils.setTextBold(highFilterBtn, hiFilter);
            ViewUtils.setTextBold(lowFilterBtn, loFilter);
        });
    }

    private void setChannelHWModeACDC(boolean acMode) {
        updateACDCButtons(acMode);
        OscillManager.runConfigTask(oscillConfig -> {
            oscillConfig.getChannelHWMode().setACMode(acMode);
            updateACDCButtons();
        });
    }

    private void updateACDCButtons() {
        OscillManager.runConfigTask(oscillConfig -> {
            updateACDCButtons(oscillConfig.getChannelHWMode().isACModeEnabled());
        });
    }

    private void updateACDCButtons(boolean acMode) {
        runOnActivity(() -> {
            ViewUtils.setTextBold(acBtn, acMode);
            ViewUtils.setTextBold(dcBtn, !acMode);
        });
    }

    private void setChannelSWMode(@NonNull ChannelSWMode.SWMode swMode) {
        updateSWModeButtons(swMode);
        OscillManager.runConfigTask(oscillConfig -> {
            oscillConfig.getChannelSWMode().setSWMode(swMode);
            updateSWModeButtons();
        });
    }

    private void updateSWModeButtons() {
        OscillManager.runConfigTask(oscillConfig -> {
            updateSWModeButtons(oscillConfig.getChannelSWMode().getSWMode());
        });
    }

    private void updateSWModeButtons(@Nullable ChannelSWMode.SWMode mode) {
        runOnActivity(() -> {
            ViewUtils.setTextBold(normBtn, mode == ChannelSWMode.SWMode.NORMAL);
            ViewUtils.setTextBold(peakBtn, mode == ChannelSWMode.SWMode.PEAK_1 || mode == ChannelSWMode.SWMode.PEAK_2);
            ViewUtils.setTextBold(avgBtn, mode == ChannelSWMode.SWMode.AVG);
            ViewUtils.setTextBold(avgHiResBtn, mode == ChannelSWMode.SWMode.AVG_HIRES);
        });
    }

    private void resetDevice() {
        OscillManager.reset();
    }

    private void connectToDevice() {
        if (OscillManager.isConnected()) {
            OscillManager.requestNextData();
        } else {
            OscillManager.init();
        }
    }

    private void onOscillConnected() {
        OscillManager.runConfigTask(oscillConfig -> {
            Oscill oscill = oscillConfig.getOscill();

            oscillConfig.getCpuTickLength().setCPUFreq(70, Dimension.MEGA);

            oscillConfig.getProcessingTypeMode()
                    .setProcessingType(ProcessingTypeMode.ProcessingType.REALTIME)
                    .setDataOutputType(ProcessingTypeMode.DataOutputType.POST_PROCESSING)
                    .setBufferType(ProcessingTypeMode.BufferType.SYNC);

            oscill.setScanDelay(0); // TD

            oscill.setDelayMaxSyncAuto(500); // TA
            oscill.setDelayMaxSyncWait(500); // TW

            oscill.setMinSamplingCount(0); // AR
            oscill.setAvgSamplingCount(0); // AP

            oscillConfig.getChannelHWMode()
                    .setChannelEnabled(true)
                    .setACMode(false)
                    .setFilter3kHz(false)
                    .setFilter3MHz(false);

            oscillConfig.getChannelSWMode().setSWMode(ChannelSWMode.SWMode.NORMAL);

            oscillConfig.getChannelSensitivity().setSensitivity(Sensitivity._200_mV);
            oscillConfig.getChannelOffset().setOffset(0f, Dimension.MILLI);

            oscillConfig.getChannelSyncMode()
                    .setSyncByFront(true)
                    .setHistFront(true)
                    .setSyncByBack(false)
                    .setHistBack(false);

            oscillConfig.getChannelSyncLevel().setNativeValue(128);
            oscillConfig.getSyncTypeMode().setSyncType(SyncTypeMode.SyncType.AUTO);

            // WARN: set last
            int maxSamplesCount = oscillConfig.getSamplesCount().getRealRange().getUpper();
            int samplesByDivCount = Math.min(maxSamplesCount / 10, 64);
            oscillConfig.getSamplesCount().setSamplesCount(10, samplesByDivCount);
            oscillConfig.getSamplingPeriod().setSamplingPeriod(SamplingTime._5_ms);
            oscillConfig.getSamplesOffset().setOffset(0f, Dimension.MILLI);

//            oscill.calibration();

            OscillManager.start();

            updateSettings();
        });
    }

    private void onOscillError(@NonNull Throwable e) {
        Log.e(TAG, e);
        ViewUtils.showToast(e.getMessage());

        resetDevice();
        updateActivityButtons();
    }

    private void initChart() {
        chart = findViewById(R.id.chart);

        chart.setBackgroundColor(Color.DKGRAY);
        chart.getDescription().setEnabled(false);
        chart.getLegend().setEnabled(false);

        chart.setDrawBorders(true);
        chart.setBorderColor(Color.GRAY);

        chart.setDrawGridBackground(false);
        chart.setTouchEnabled(true);
        chart.setDragEnabled(true);
        chart.setScaleEnabled(false);
        chart.setPinchZoom(false);
        chart.setHighlightPerDragEnabled(false);
        chart.setHighlightPerTapEnabled(false);

        initXAxis(chart.getXAxis());

        initYAxis(chart.getAxisLeft());
        initYAxis(chart.getAxisRight());
    }

    private void initYAxis(@NonNull YAxis yAxis) {
        yAxis.enableGridDashedLine(2f, 2f, 0f);
        yAxis.setDrawGridLinesBehindData(false);
        yAxis.setZeroLineWidth(2f);
        yAxis.setGridColor(Color.GRAY);
        yAxis.setAxisLineColor(Color.GRAY);
        yAxis.setTextColor(Color.WHITE);
        yAxis.setLabelCount(8);
        yAxis.setValueFormatter(new UnitFormatter(new Unit(Dimension.MILLI, Unit.VOLT)));
    }

    private void initXAxis(@NonNull XAxis xAxis) {
        xAxis.setPosition(XAxis.XAxisPosition.BOTH_SIDED);
        xAxis.setGridColor(Color.GRAY);
        xAxis.setAxisLineColor(Color.GRAY);
        xAxis.setTextColor(Color.WHITE);
        xAxis.setAvoidFirstLastClipping(false);
        xAxis.enableGridDashedLine(2f, 2f, 0f);
        xAxis.setDrawGridLinesBehindData(false);
        xAxis.setLabelCount(10); // TODO: time div count
        xAxis.setValueFormatter(new UnitFormatter(new Unit(Dimension.MILLI, Unit.SECOND)));
    }

    private ArrayListEx<Entry> values = new ArrayListEx<>(0);
    private ArrayListEx<Entry> valuesFFT = new ArrayListEx<>(0);

    private void prepareData(@NonNull OscillData oscillData) {
        Executor.runInSyncQueue2(() -> {
            float[] tData = oscillData.getTimeData();
            float[] vData = oscillData.getVoltData();
//        float[] vData2 = oscillData.getVoltData2();

/*
            ComplexArray fft = oscillData.getFFT();
            ComplexArray fftData = fft.getMagnitudePhase();
*/
            float minV = oscillData.getMinV();

            int dataSize = oscillData.getDataSize();

            ArrayListEx<Entry> values = this.values;
            if (values.size() != dataSize) {
                values = new ArrayListEx<>(dataSize);
                for (int idx = 0; idx < dataSize; idx++) {
                    values.add(new Entry(tData[idx], vData[idx]));
                }
                this.values = values;
            } else {
                Entry entry;
                for (int idx = 0; idx < dataSize; idx++) {
                    entry = values.get(idx);
                    entry.setX(tData[idx]);
                    entry.setY(vData[idx]);
                }
            }

/*
            int fftDataSize = fftData.length();
            float[] fftDataMagn = fftData.re();

            ArrayListEx<Entry> valuesFFT = this.valuesFFT;
            if (valuesFFT.size() != fftDataSize) {
                valuesFFT = new ArrayListEx<>(fftDataSize);
                for (int idx = 0; idx < fftDataSize; idx++) {
                    valuesFFT.add(new Entry(tData[idx] * 2f, minV + fftDataMagn[idx]));
                }
                this.valuesFFT = valuesFFT;
            } else {
                Entry entry;
                for (int idx = 0; idx < fftDataSize; idx++) {
                    entry = valuesFFT.get(idx);
                    entry.setX(tData[idx] * 2f);
                    entry.setY(minV + fftDataMagn[idx]);
                }
            }
*/

            Executor.runInUIThreadAsync(() -> setData(oscillData, this.values, this.valuesFFT));
        });
    }

    private void updateYAxis(@NonNull YAxis yAxis, @NonNull OscillData oscillData) {
        float maxV = oscillData.getMaxV();
        float minV = oscillData.getMinV();

        yAxis.setAxisMaximum(maxV);
        yAxis.setAxisMinimum(minV);

        yAxis.setZeroLineWidth(2f);
    }

    private void updateTriggerMarker(@NonNull LineData data, @NonNull OscillData oscillData) {
        float triggerV = oscillData.getTriggerV();
        float[] timeData = oscillData.getTimeData();

        List<Entry> triggerData = new ArrayList<>(8);
        if (timeData.length > 10) {
            triggerData.add(new Entry(timeData[0], triggerV));
            triggerData.add(new Entry(timeData[timeData.length - 1], triggerV));
        }

        LineDataSet triggerDataSet = (LineDataSet) data.getDataSetByIndex(1);
        triggerDataSet.setEntries(triggerData);
        triggerDataSet.notifyDataSetChanged();
    }

    private void setData(@NonNull OscillData oscillData, @NonNull List<Entry> valuesV, @NonNull List<Entry> valuesFFT) {
        updateDataInfo(oscillData);

        updateYAxis(chart.getAxisLeft(), oscillData);
        updateYAxis(chart.getAxisRight(), oscillData);

        LineDataSet dataSet;
        LineDataSet fftDataSet;
        LineData data = chart.getData();

        if (data != null && data.getDataSetCount() > 0) {
            dataSet = (LineDataSet) data.getDataSetByIndex(0);
            dataSet.setEntries(valuesV);

            updateTriggerMarker(data, oscillData);

//            fftDataSet = (LineDataSet) data.getDataSetByIndex(2);
//            fftDataSet.setEntries(valuesFFT);

            data.notifyDataChanged();

            if (updateChart.compareAndSet(true, false)) {
                chart.notifyDataSetChanged();
            }
            chart.invalidate();

        } else {
            ArrayList<ILineDataSet> dataSets = new ArrayList<>(8);

            dataSet = initDataLine();
            dataSet.setEntries(valuesV);
            dataSets.add(dataSet); // 0

            LineDataSet triggerMarker = initTriggerMarker();
            dataSets.add(triggerMarker); // 1

//            fftDataSet = initFFTLine();
//            fftDataSet.setEntries(valuesFFT);
//            dataSets.add(fftDataSet); // 2

            data = new LineData(dataSets);
            chart.setData(data);
        }
    }

    final Unit voltUnit = new Unit(Dimension.MILLI, Unit.VOLT);

    private void updateDataInfo(@NonNull OscillData oscillData) {
        ViewUtils.setText(vMinText, voltUnit.format(oscillData.getVDataMin(), 0));
        ViewUtils.setText(vMaxText, voltUnit.format(oscillData.getVDataMax(), 0));
        ViewUtils.setText(vAvgText, voltUnit.format(oscillData.getVDataAvg(), 0));
    }

    static class LineDataSetEx extends LineDataSet {

        LineDataSetEx(List<Entry> yVals, String label) {
            super(yVals, label);
        }

        @Override
        public void calcMinMax() {
            if (mEntries != null && !mEntries.isEmpty()) {
                Entry first = mEntries.get(0);
                Entry last = mEntries.get(mEntries.size() - 1);
                mXMin = first.getX();
                mXMax = last.getX();
            }
        }
    }

    @NonNull
    private LineDataSet initDataLine() {
        LineDataSet dataSet = new LineDataSetEx(null, null);

        dataSet.setDrawIcons(false);
        dataSet.setDrawCircles(false);
        dataSet.setDrawCircleHole(false);
        dataSet.setDrawValues(false);
        dataSet.setDrawFilled(false);

        dataSet.setColor(Color.argb(0xFF, 0x00, 0xFF, 0xFF));
        dataSet.setLineWidth(0.8f);

        return dataSet;
    }

    @NonNull
    private LineDataSet initTriggerMarker() {
        LineDataSet dataSet = new LineDataSetEx(null, null);
        dataSet.setDrawIcons(false);
        dataSet.setDrawCircles(false);
        dataSet.setDrawCircleHole(false);
        dataSet.setDrawValues(false);
        dataSet.setDrawFilled(false);

        dataSet.setColor(Color.GREEN);
        dataSet.setLineWidth(1f);

        return dataSet;
    }

    @NonNull
    private LineDataSet initFFTLine() {
        LineDataSet dataSet = new LineDataSetEx(null, null);

        dataSet.setDrawIcons(false);
        dataSet.setDrawCircles(false);
        dataSet.setDrawCircleHole(false);
        dataSet.setDrawValues(false);
        dataSet.setDrawFilled(false);

        dataSet.setColor(Color.YELLOW);
        dataSet.setLineWidth(1f);

        return dataSet;
    }
}
