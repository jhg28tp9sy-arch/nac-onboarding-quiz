const studyKey = "nac-connect:study-list:v1";

export default function ({ data, setStateValue, setTriggerValue }) {
    function readStudyList() {
        try {
            const saved = JSON.parse(localStorage.getItem(studyKey) ?? "[]");
            return Array.isArray(saved) ? saved : [];
        } catch {
            return data.study ?? [];
        }
    }

    if (data.edit) {
        const [id, save] = data.edit;
        const saved = new Set(readStudyList());
        if (save) saved.add(id);
        else saved.delete(id);
        const updated = Array.from(saved);
        try {
            localStorage.setItem(studyKey, JSON.stringify(updated));
        } catch {
            // The signed-in session still supports pins when device storage is unavailable.
        }
        setStateValue("study", updated);
    } else if (data.study === null) {
        setStateValue("study", readStudyList());
    }

    function focusChart(event) {
        const control = event.target.closest(".nac-org-tree [data-chart-focus], .nac-chart-path [data-chart-focus]");
        if (!control) return;
        document.querySelector(".st-key-chart_search")?.scrollIntoView({ block: "start" });
        setTriggerValue("focus", control.dataset.chartFocus);
    }

    function syncStudyList(event) {
        if (event.key === studyKey || event.key === null) setStateValue("study", readStudyList());
    }

    document.addEventListener("click", focusChart);
    window.addEventListener("storage", syncStudyList);
    return () => {
        document.removeEventListener("click", focusChart);
        window.removeEventListener("storage", syncStudyList);
    };
}
