(function () {
    const createTestForm = document.getElementById("create-test-form");

    /**
     * Create new test config
     */
    createTestForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const form = e.target;
        const payload = {
            course_id: form.course_id.value,
            lesson_id: form.lesson_id.value,
            server_host: form.server_host.value,
            test_user_num: form.test_user_num.value,
            target_ptc_id: form.target_ptc_id.value || null,
            with_local_tester: form.with_local_tester.checked,
        }

        fetch(form.action, {
            method: form.method.toUpperCase(),
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(_ => {
            window.location.reload();
        })
    })

    /**
     * Manipulate active test config
     */
    const activeInfoForm = document.getElementById("active-info");
    const startTestBtn = document.getElementById("start-test")
    const modifyTestBtn = document.getElementById("modify-test")
    const deleteTestBtn = document.getElementById("delete-test")

    startTestBtn && startTestBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!confirm("테스트를 시작하실 건가요?")) return;

        const url = activeInfoForm.dataset.startUrl;
        const payload = { duration: activeInfoForm.duration.value || null }

        if (payload.duration == null) {
            window.alert("시간 값을 입력해주세요.")
            return;
        }

        fetch(url, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(_ => {
            window.location.reload();
        })
    })

    modifyTestBtn && modifyTestBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!confirm("테스트를 수정하실 건가요?")) return;

        const url = activeInfoForm.dataset.startUrl;
        const payload = {
            server_host: activeInfoForm.server_host.value,
            target_ptc_id: activeInfoForm.target_ptc_id.value || null,
            duration: activeInfoForm.duration.value || null,
        }

        fetch(url, {
            method: "PUT",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(_ => {
            window.location.reload();
        })
    })

    deleteTestBtn && deleteTestBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!confirm("테스트를 삭제하실 건가요?")) return;

        const url = activeInfoForm.dataset.deleteUrl;
        fetch(url, {
            method: "DELETE",
            headers: { 'Content-Type': 'application/json' },
        }).then(_ => {
            window.location.reload();
        })
    })

    const remainingTime = document.getElementById("test-remaining");
    let endDate;

    if (remainingTime) {
        endDate = new Date(remainingTime.dataset.endAt);

        setInterval(() => {
            remainingTime.value = intComma(parseInt((endDate.getTime() - new Date().getTime()) / 1000))
        }, 1000)
    }

}())