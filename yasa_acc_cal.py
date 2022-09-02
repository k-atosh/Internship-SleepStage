import mne
import numpy as np
import pandas as pd
import yasa
from mne.datasets.sleep_physionet.age import fetch_data
from sklearn.metrics import accuracy_score

annotation_desc_2_event_id = {
    "Sleep stage W": 1,
    "Sleep stage 1": 2,
    "Sleep stage 2": 3,
    "Sleep stage 3": 4,
    "Sleep stage 4": 4,
    "Sleep stage R": 5,
}

# create a new event_id that unifies stages 3 and 4
event_id = {
    "Sleep stage W": 1,
    "Sleep stage 1": 2,
    "Sleep stage 2": 3,
    "Sleep stage 3/4": 4,
    "Sleep stage R": 5,
}


# Pattern 1: 0, x, x, ... x, x, 0 (1 < x < 4)
# Pattern 2: 0, 2, 2, 3, ...
def check_trans(array, index, current, count):
    stage = array[index + 1]

    # 0, 2, 2, ... 2, 0
    if stage == 0:
        return ["Pattern 1", count]

    elif stage != 0 and stage != current:
        # 0, 2, 2, 3, ...
        if current == 2 and stage == 3:
            return ["Pattern 2", 0]

        return ["NIL", 0]

    # 同じステージだったら、調査位置とカウントを1増やして再帰
    elif stage == current:
        return check_trans(array, index + 1, current, count + 1)


def fix_hypno(array):
    size = array.shape[0]
    res = [False, 0]

    for i in range(size - 1):
        # パターン調査
        if array[i] == 0:
            # 0, 0, 2, ... の並び
            if array[i + 1] == 2:
                count = 0
                res = check_trans(array, i, 2, count)

            # 0, 0, 3, ... の並び
            if array[i + 1] == 3:
                count = 0
                res = check_trans(array, i, 3, count)

        # 修正
        # Pattern 1: 指定範囲を全て0に置換
        if res[0] == "Pattern 1" and res[1] != 0:
            array[i + 1] = 0
            res[1] -= 1
            if res[1] == 0:
                res[0] = "NIL"

        # Pattern 2: Pattern 2が始まる直前の0を1に置換
        if res[0] == "Pattern 2":
            array[i] = 1
            res[0] = "NIL"


def fetch(amount):
    # [[edf1, edf2, ...], [hypno1, hypno2, ...]]
    DataList = [[], []]

    NAN_data = [39, 68, 69, 78, 79]
    for NAN in NAN_data:
        if amount - 1 > NAN:
            amount += 1

    for i in range(amount):
        [data] = fetch_data(subjects=[0], recording=[1])
        DataList[0].append(data)
        print(DataList[0])

        edf = mne.io.read_raw_edf(
            DataList[0][i][0], stim_channel="Event marker", misc=["Temp rectal"]
        )

        annot = mne.read_annotations(DataList[0][i][1])
        edf.set_annotations(annot, emit_warning=False)

        events, _ = mne.events_from_annotations(
            edf, event_id=annotation_desc_2_event_id, chunk_duration=30.0
        )

        tmax = 30.0 - 1.0 / edf.info["sfreq"]

        epochs_test = mne.Epochs(
            raw=edf,
            events=events,
            event_id=event_id,
            tmin=0.0,
            tmax=tmax,
            baseline=None,
        )

        hypno = epochs_test.events[:, 2] - 1
        DataList[1].append(hypno)

    return DataList


sls = yasa.SleepStaging(edf, eeg_name="EEG Fpz-Cz")
hypno_pred = sls.predict()
hypno_pred = yasa.hypno_str_to_int(hypno_pred)

csv_pre = pd.DataFrame(hypno_pred)
csv_pre.to_csv("./csv_pre.csv")

# hypno_pred = np.array([0,0,0,2,2,0,0,2,3,0])
fixed = np.copy(hypno_pred)

fix_hypno(fixed)

acc_bef = accuracy_score(hypno, hypno_pred)  # 修正前の正解率
# acc_case1 = accuracy_score(hypno, fix_case1)
acc_aft = accuracy_score(hypno, fixed)  # 修正後の正解率
# acc_case3 = accuracy_score(hypno, fix_case3)

print("正解率")
print("  修正前", acc_bef)
# print('  修正後(方法1)', acc_case1)
print("  修正後", acc_aft)
# print('  修正後(方法3)', acc_case3)
