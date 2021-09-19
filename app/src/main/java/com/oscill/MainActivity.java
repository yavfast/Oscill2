package com.oscill;

import android.graphics.Color;
import android.os.Bundle;
import android.widget.Button;
import android.widget.ImageView;
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
import com.oscill.controller.config.ChanelSWMode;
import com.oscill.controller.config.ProcessingTypeMode;
import com.oscill.controller.config.SamplingTime;
import com.oscill.controller.config.Sensitivity;
import com.oscill.controller.config.SyncTypeMode;
import com.oscill.events.OnOscillConnected;
import com.oscill.events.OnOscillData;
import com.oscill.events.OnOscillError;
import com.oscill.types.Dimension;
import com.oscill.utils.Log;
import com.oscill.utils.StringUtils;
import com.oscill.utils.ViewUtils;
import com.oscill.utils.executor.EventHolder;
import com.oscill.utils.executor.EventsController;
import com.oscill.utils.executor.Executor;

import java.util.ArrayList;

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
    TextView hiResBtn;

    TextView acdcBtn;
    TextView gndBtn;
    TextView highFilterBtn;
    TextView lowFilterBtn;

    ImageView triggerStartBtn;
    ImageView triggerEndBtn;
    ImageView triggerFreeBtn;

    ImageView voltUpBtn;
    ImageView voltDownBtn;
    TextView voltDivText;

    ImageView timeUpBtn;
    ImageView timeDownBtn;
    TextView timeDivText;

    private final EventHolder<?> onOscillConnected = EventsController.onReceiveEvent(this, OnOscillConnected.class, event ->
            onOscillConnected()
    );

    private final EventHolder<?> onOscillData = EventsController.onReceiveEventAsync(this, OnOscillData.class, event ->
            prepareData(event.oscillData)
    );

    private final EventHolder<?> onOscillError = EventsController.onReceiveEvent(this, OnOscillError.class, event ->
            onOscillError(event.getError())
    );

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
            setSWMode(ChanelSWMode.SWMode.NORMAL)
        );

        peakBtn = findViewById(R.id.peakBtn);
        peakBtn.setOnClickListener(v ->
            setSWMode(ChanelSWMode.SWMode.PEAK_1)
        );
        avgBtn = findViewById(R.id.avgBtn);
        avgBtn.setOnClickListener(v ->
            setSWMode(ChanelSWMode.SWMode.AVG)
        );
        hiResBtn = findViewById(R.id.hiResBtn);
        hiResBtn.setOnClickListener(v ->
            setSWMode(ChanelSWMode.SWMode.AVG_HIRES)
        );

        gndBtn = findViewById(R.id.gndBtn);
        gndBtn.setOnClickListener(v -> {

        });

        acdcBtn = findViewById(R.id.acdcBtn);
        acdcBtn.setOnClickListener(v -> {

        });
        highFilterBtn = findViewById(R.id.highFilterBtn);
        highFilterBtn.setOnClickListener(v -> {

        });
        lowFilterBtn = findViewById(R.id.lowFilterBtn);
        lowFilterBtn.setOnClickListener(v -> {

        });

        triggerStartBtn = findViewById(R.id.triggerStartBtn);
        triggerStartBtn.setOnClickListener(v -> {

        });
        triggerEndBtn = findViewById(R.id.triggerEndBtn);
        triggerEndBtn.setOnClickListener(v -> {

        });
        triggerFreeBtn = findViewById(R.id.triggerFreeBtn);
        triggerFreeBtn.setOnClickListener(v -> {

        });

        voltUpBtn = findViewById(R.id.voltUpBtn);
        voltUpBtn.setOnClickListener(v ->
            doChangeVoltByDiv(+1)
        );
        voltDownBtn = findViewById(R.id.voltDownBtn);
        voltDownBtn.setOnClickListener(v ->
            doChangeVoltByDiv(-1)
        );
        voltDivText = findViewById(R.id.voltDivText);

        timeUpBtn = findViewById(R.id.timeUpBtn);
        timeUpBtn.setOnClickListener(v -> {
            doChangeTimeByDiv(+1);
        });
        timeDownBtn = findViewById(R.id.timeDownBtn);
        timeDownBtn.setOnClickListener(v -> {
            doChangeTimeByDiv(-1);
        });
        timeDivText = findViewById(R.id.timeDivText);

        initChart();
        chart.setOnClickListener(v ->
                OscillManager.requestNextData()
        );

        EventsController.resumeEvents(onOscillConnected, onOscillData, onOscillError);
        connectToDevice();
    }

    private void doChangeVoltByDiv(int step) {
        OscillManager.runConfigTask(oscillConfig -> {
            Sensitivity curSensitivity = oscillConfig.getChannelSensitivity().getSensitivity();
            Sensitivity newSensitivity = curSensitivity.getNext(step);

            oscillConfig.getChannelSensitivity().setSensitivity(newSensitivity);
            updateVoltByDiv();
        });
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
        EventsController.resumeEvents(onOscillConnected, onOscillData, onOscillError);
    }

    @Override
    protected void onPause() {
        EventsController.pauseEvents(onOscillConnected, onOscillData, onOscillError);
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

    private void setSWMode(@NonNull ChanelSWMode.SWMode swMode) {
        updateSWModeButtons(swMode);
        OscillManager.runConfigTask(oscillConfig -> {
            oscillConfig.getChanelSWMode().setSWMode(swMode);
            updateSWModeButtons(oscillConfig.getChanelSWMode().getSWMode());
        });
    }

    private void updateSWModeButtons(@Nullable ChanelSWMode.SWMode mode) {
        runOnActivity(() -> {
            normBtn.setPressed(mode == ChanelSWMode.SWMode.NORMAL);
            peakBtn.setPressed(mode == ChanelSWMode.SWMode.PEAK_1);
            avgBtn.setPressed(mode == ChanelSWMode.SWMode.AVG);
            hiResBtn.setPressed(mode == ChanelSWMode.SWMode.AVG_HIRES);
        });
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

            oscillConfig.getCpuTickLength().setCPUFreq(60, Dimension.MEGA);

            oscillConfig.getProcessingTypeMode()
                    .setProcessingType(ProcessingTypeMode.ProcessingType.REALTIME)
                    .setDataOutputType(ProcessingTypeMode.DataOutputType.POST_PROCESSING)
                    .setBufferType(ProcessingTypeMode.BufferType.SYNC);

            oscill.setScanDelay(0); // TD

            oscill.setDelayMaxSyncAuto(500); // TA
            oscill.setDelayMaxSyncWait(500); // TW

            oscill.setMinSamplingCount(0); // AR
            oscill.setAvgSamplingCount(0); // AP

            oscillConfig.getChanelHWMode()
                    .setChanelEnabled(true)
                    .setACMode(false)
                    .setFilter3kHz(false)
                    .setFilter3MHz(false);

            oscillConfig.getChanelSWMode().setSWMode(ChanelSWMode.SWMode.NORMAL);

            oscillConfig.getChannelSensitivity().setSensitivity(Sensitivity._200_mV);
            oscillConfig.getChanelOffset().setOffset(0f, Dimension.MILLI);

            oscillConfig.getChanelSyncMode()
                    .setSyncByFront(true)
                    .setHistFront(false);

            oscillConfig.getChanelSyncLevel().setNativeValue(20);
            oscillConfig.getSyncTypeMode().setSyncType(SyncTypeMode.SyncType.FREE);

            // WARN: set last
            oscillConfig.getSamplesCount().setSamplesCount(10, 32);
            oscillConfig.getSamplingPeriod().setSamplingPeriod(SamplingTime._1_ms);
            oscillConfig.getSamplesOffset().setOffset(0f, Dimension.MILLI);

            oscill.calibration();

            OscillManager.start();

            updateSettings();
        });
    }

    private void updateSettings() {
        runOnActivity(() -> {
            updateActivityButtons();
            updateVoltByDiv();
            updateTimeByDiv();
        });
    }

    private void onOscillError(@NonNull Throwable e) {
        Log.e(TAG, e);
        ViewUtils.showToast(e.getMessage());
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
        chart.setScaleEnabled(true);
        chart.setPinchZoom(true);

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
    }

    private void initXAxis(@NonNull XAxis xAxis) {
        xAxis.setPosition(XAxis.XAxisPosition.BOTH_SIDED);
        xAxis.setGridColor(Color.GRAY);
        xAxis.setAxisLineColor(Color.GRAY);
        xAxis.setTextColor(Color.WHITE);
        xAxis.setAvoidFirstLastClipping(false);
        xAxis.enableGridDashedLine(2f, 2f, 0f);
        xAxis.setDrawGridLinesBehindData(false);
        xAxis.setLabelCount(10);
    }

    private void prepareData(@NonNull OscillData oscillData) {
        float[] tData = oscillData.tData;
        float[] vData = oscillData.vData;
        int dataSize = oscillData.dataSize;

        ArrayList<Entry> values = new ArrayList<>(dataSize);
        for (int idx = 0; idx < dataSize; idx++) {
            values.add(new Entry(tData[idx], vData[idx]));
        }

        Executor.runInUIThreadAsync(() -> setData(oscillData, values));
    }

    private void updateYAxis(@NonNull YAxis yAxis, @NonNull OscillData oscillData) {
        float maxV = oscillData.getMaxV();
        float minV = oscillData.getMinV();

        yAxis.setAxisMaximum(maxV);
        yAxis.setAxisMinimum(minV);
    }

    private void setData(@NonNull OscillData oscillData, @NonNull ArrayList<Entry> values) {
        updateYAxis(chart.getAxisLeft(), oscillData);
        updateYAxis(chart.getAxisRight(), oscillData);

        LineDataSet dataSet;
        LineData data = chart.getData();

        if (data != null && data.getDataSetCount() > 0) {
            dataSet = (LineDataSet) data.getDataSetByIndex(0);
            dataSet.setValues(values);
            dataSet.notifyDataSetChanged();
            data.notifyDataChanged();
            chart.notifyDataSetChanged();
            chart.invalidate();

        } else {
            dataSet = new LineDataSet(values, null);

            dataSet.setDrawIcons(false);
            dataSet.setDrawCircles(false);
            dataSet.setDrawCircleHole(false);
            dataSet.setDrawValues(false);
            dataSet.setDrawFilled(false);

            dataSet.setColor(Color.CYAN);
            dataSet.setLineWidth(2f);

            ArrayList<ILineDataSet> dataSets = new ArrayList<>();
            dataSets.add(dataSet);

            data = new LineData(dataSets);
            chart.setData(data);
        }
    }

}
