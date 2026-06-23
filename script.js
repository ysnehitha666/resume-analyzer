// ===== Show file name when PDF is uploaded =====
function showFileName() {
    const fileInput = document.getElementById('resumeFile');
    const fileName = document.getElementById('fileName');

    if (fileInput.files.length > 0) {
        fileName.textContent = "✅ " + fileInput.files[0].name + " selected!";
    }
}


// ===== Upload + Analyze resume =====
function startAnalysis() {
    const fileInput = document.getElementById('resumeFile');

    if (fileInput.files.length === 0) {
        alert("⚠️ Please upload a PDF file first!");
        return;
    }

    document.getElementById('featuresSection').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('loading').style.display = 'block';

    const formData = new FormData();
    formData.append('resume', fileInput.files[0]);

    fetch('/analyze', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('results').style.display = 'block';

        if (data.error) {
            document.getElementById('results').innerHTML = `
                <div class="feedback-card" style="border-left-color:#dc2626;">
                    <div class="feedback-icon">❌</div>
                    <div class="feedback-content">
                        <h3>Something went wrong</h3>
                        <p>${data.error}</p>
                    </div>
                </div>
            `;
            return;
        }

        document.getElementById('statScore').textContent = data.ats_score.split('/')[0] || data.ats_score;
        document.getElementById('statGaps').textContent = data.missing_skills.split(',').length;
        document.getElementById('statStrengths').textContent = data.strengths.split(',').length;

        document.getElementById('missingSkillsText').textContent = data.missing_skills;
        document.getElementById('suggestionText').textContent = data.suggestion;
        document.getElementById('strengthsText').textContent = data.strengths;
    })
    .catch(error => {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('results').style.display = 'block';
        document.getElementById('results').innerHTML = `
            <div class="feedback-card" style="border-left-color:#dc2626;">
                <div class="feedback-icon">❌</div>
                <div class="feedback-content">
                    <h3>Something went wrong</h3>
                    <p>Please check that the server is running and try again.</p>
                </div>
            </div>
        `;
    });
}


// ===== Load past analyses (history) =====
function loadHistory() {
    document.getElementById('compareSection').innerHTML = '';

    fetch('/history')
    .then(response => response.json())
    .then(data => {
        const historySection = document.getElementById('historySection');

        if (data.length === 0) {
            historySection.innerHTML = '<p style="text-align:center; color:#9ca3af; font-size:14px;">No history yet. Analyze a resume first!</p>';
            return;
        }

        let html = '<h2 style="font-size:15px; color:#1e3a8a; margin-bottom:14px;">Past Analyses</h2>';

        data.forEach(item => {
            html += `
                <div class="history-item">
                    <div class="history-item-header">
                        <span class="history-filename">📄 ${item.filename}</span>
                        <span class="history-score">${item.ats_score}</span>
                    </div>
                    <p style="font-size:13px; color:#6b7280; margin:0 0 6px;">${item.suggestion}</p>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="history-date">🕒 ${item.created_at}</span>
                        <button onclick="deleteHistoryItem(${item.id})" style="background:none; border:none; color:#dc2626; font-size:12px; cursor:pointer; font-weight:600;">🗑️ Delete</button>
                    </div>
                </div>
            `;
        });

        historySection.innerHTML = html;
    })
    .catch(error => {
        document.getElementById('historySection').innerHTML = '<p style="color:red; text-align:center;">Failed to load history</p>';
    });
}


// ===== Load resume list for comparison dropdowns =====
function loadCompareOptions() {
    document.getElementById('historySection').innerHTML = '';

    fetch('/history')
    .then(response => response.json())
    .then(data => {
        const compareSection = document.getElementById('compareSection');

        if (data.length < 2) {
            compareSection.innerHTML = '<p style="text-align:center; color:#9ca3af; font-size:14px;">You need at least 2 analyses to compare. Analyze more resumes first!</p>';
            return;
        }

        let optionsHTML = '';
        data.forEach(item => {
            optionsHTML += `<option value="${item.id}">${item.filename} (Score: ${item.ats_score})</option>`;
        });

        compareSection.innerHTML = `
            <div class="compare-select-box">
                <label>Resume A</label>
                <select id="resumeA">${optionsHTML}</select>
            </div>
            <div class="compare-select-box">
                <label>Resume B</label>
                <select id="resumeB">${optionsHTML}</select>
            </div>
            <button class="compare-submit-btn" onclick="runComparison()">🔍 Compare These Resumes</button>
            <div id="compareResultBox"></div>
        `;
    });
}


// ===== Run the AI comparison =====
function runComparison() {
    const id1 = document.getElementById('resumeA').value;
    const id2 = document.getElementById('resumeB').value;

    if (id1 === id2) {
        alert("⚠️ Please select two different resumes to compare!");
        return;
    }

    const resultBox = document.getElementById('compareResultBox');
    resultBox.innerHTML = '<p style="text-align:center; color:#6b7280; margin-top:15px;">🤖 AI is comparing... please wait</p>';

    fetch('/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id1: id1, id2: id2 })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            resultBox.innerHTML = `<p style="color:red; text-align:center;">${data.error}</p>`;
            return;
        }

        resultBox.innerHTML = `
            <div class="compare-result">
                <div class="compare-winner">🏆 Winner: ${data.winner}</div>
                <p><strong>Why:</strong> ${data.reason}</p>
                <p><strong>💡 Tip:</strong> ${data.recommendation}</p>
            </div>
        `;
    })
    .catch(error => {
        resultBox.innerHTML = '<p style="color:red; text-align:center;">Something went wrong. Try again.</p>';
    });
}


// ===== Delete a history item =====
function deleteHistoryItem(id) {
    if (!confirm("Delete this analysis from history?")) {
        return;
    }

    fetch(`/history/${id}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadHistory(); // Refresh the list
        }
    })
    .catch(error => {
        alert("Failed to delete. Try again.");
    });
}