"""
Textual CSS styles for isiMotor Pulse Manager.
"""

APP_CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

#top-nav-bar {
    layout: horizontal;
    height: 3;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
}

#main-nav-tabs {
    width: 1fr;
    height: 100%;
    background: transparent;
}

#metrics-bar {
    layout: horizontal;
    height: 3;
    margin: 1 1 0 1;
    background: #161b22;
    border: tall #30363d;
}

.metric-box {
    width: 1fr;
    content-align: center middle;
    text-align: center;
    padding: 0 1;
}

#main-content-switcher {
    height: 1fr;
    margin: 0 1;
}

/* ── 1. Home View Styles ────────────────────────────────────────── */
#view-home {
    height: 100%;
    layout: vertical;
    padding: 0 0;
}

#home-hero-banner {
    height: 3;
    background: #161b22;
    border: round #58a6ff;
    margin: 1 0 0 0;
    content-align: center middle;
    text-align: center;
}

#home-cards-container {
    layout: horizontal;
    height: 1fr;
    margin: 1 0 0 0;
}

.home-card {
    width: 1fr;
    height: 100%;
    background: #161b22;
    border: round #30363d;
    padding: 1 1;
    margin: 0 1;
    layout: vertical;
}

.home-card-header {
    text-align: center;
    text-style: bold;
    padding-bottom: 0;
    border-bottom: solid #30363d;
    margin-bottom: 1;
    height: 2;
}

.home-card-content {
    height: 1fr;
}

.home-card-actions {
    layout: horizontal;
    height: 3;
    margin-top: 1;
}

.home-card-btn {
    width: 1fr;
    margin: 0 1;
    height: 3;
}

/* ── 2. Install / Config Form Styles ────────────────────────────── */
#view-install {
    height: 100%;
    layout: vertical;
}

#install-controls {
    layout: horizontal;
    height: auto;
    padding: 0 1;
    margin: 1 0 0 0;
    background: #161b22;
    border-bottom: solid #30363d;
    align: left middle;
}

#install-form-container {
    height: 1fr;
    layout: horizontal;
    margin: 1 0 0 0;
}

.cfg-column {
    width: 1fr;
    height: 100%;
    layout: vertical;
    overflow-y: auto;
    padding: 0 1;
}

.form-section-card {
    background: #161b22;
    border: round #58a6ff;
    padding: 1 2;
    margin: 0 0 1 0;
    layout: vertical;
    height: auto;
}

.form-section-title {
    text-style: bold;
    color: #58a6ff;
    border-bottom: solid #30363d;
    padding-bottom: 0;
    margin-bottom: 1;
}

.cfg-form-row {
    layout: horizontal;
    height: 3;
    margin-bottom: 1;
    align: left middle;
}

.cfg-label {
    width: 1fr;
    color: #c9d1d9;
    text-style: bold;
}

.cfg-input-text {
    width: 20;
    height: 3;
    background: #0d1117;
    border: solid #30363d;
    color: #ffffff;
}

.cfg-input-text:focus {
    border: double #58a6ff;
}

.cfg-select-box {
    width: 20;
    height: 3;
}

.cfg-rate-row {
    layout: horizontal;
    height: 3;
    margin-bottom: 1;
    align: left middle;
}

.cfg-rate-label {
    width: 1fr;
    color: #c9d1d9;
}

.cfg-rate-select {
    width: 16;
    height: 3;
    margin-right: 1;
}

.cfg-rate-input-box {
    width: auto;
    height: 3;
    layout: horizontal;
    align: left middle;
}

.cfg-rate-hz-input {
    width: 8;
    height: 3;
    background: #0d1117;
    border: solid #30363d;
    color: #58a6ff;
    text-style: bold;
}

.cfg-rate-hz-input:focus {
    border: double #3fb950;
}

.cfg-hz-unit {
    width: auto;
    padding: 0 1 0 1;
    color: #58a6ff;
    text-style: bold;
}

#cfg-target-info {
    height: auto;
    padding: 0;
}

/* ── 3. Explorer View Styles ────────────────────────────────────── */
#view-explorer {
    height: 100%;
    layout: vertical;
}

#explorer-controls {
    layout: horizontal;
    height: 3;
    margin: 1 0 0 0;
    background: #161b22;
    border-top: solid #30363d;
    border-bottom: solid #30363d;
    align: left middle;
}

#packet-tabs {
    width: auto;
    height: 100%;
    background: transparent;
}

#search-box {
    width: 1fr;
    height: 100%;
    margin: 0 1;
    background: #0d1117;
    border: none;
    color: #c9d1d9;
}

#table-container-explorer {
    height: 1fr;
    margin: 1 0 0 0;
    background: #161b22;
    border: round #58a6ff;
}

/* ── 4. Commands View Styles ────────────────────────────────────── */
#view-commands {
    height: 100%;
    layout: vertical;
}

#commands-status-bar {
    height: 3;
    margin: 1 0 0 0;
    background: #161b22;
    border-top: solid #30363d;
    border-bottom: solid #30363d;
    content-align: center middle;
    text-align: center;
}

#commands-panels-container {
    layout: horizontal;
    height: auto;
    margin: 1 0 0 0;
}

.cmd-panel {
    width: 1fr;
    background: #161b22;
    border: round #30363d;
    padding: 1;
    margin: 0 1;
    layout: vertical;
}

.cmd-panel-title {
    text-align: center;
    text-style: bold;
    color: #e3b341;
    border-bottom: solid #30363d;
    padding-bottom: 1;
    margin-bottom: 1;
}

.cmd-btn {
    width: 100%;
    margin-bottom: 1;
    height: 3;
}

.cmd-grid {
    layout: grid;
    grid-size: 2;
    grid-gutter: 1;
}

#input-cmd-name {
    margin-bottom: 1;
    height: 3;
}

#input-cmd-val {
    margin-bottom: 1;
    height: 3;
}

#table-container-commands {
    height: 1fr;
    margin: 1 0 0 0;
    background: #161b22;
    border: round #58a6ff;
}

/* Common Actions & Tables */
.actions-box {
    layout: horizontal;
    width: auto;
    height: 100%;
    align: right middle;
}

.btn-action {
    margin: 0 1;
    min-width: 15;
    height: 3;
    text-style: bold;
}

#btn-cfg-save {
    background: #238636;
    color: #ffffff;
}

#btn-cfg-reset {
    background: #d29922;
    color: #000000;
}

#btn-install-copy-dll {
    background: #1f6feb;
    color: #ffffff;
}

#btn-install-refresh, #btn-install-copy-json {
    background: #30363d;
    color: #ffffff;
}

#btn-explorer-copy-json {
    background: #1f6feb;
    color: #ffffff;
}

#btn-explorer-copy-table, #btn-explorer-reset-stats {
    background: #30363d;
    color: #ffffff;
}

DataTable {
    height: 100%;
    width: 100%;
    background: #161b22;
}

DataTable > .datatable--header {
    background: #21262d;
    color: #58a6ff;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1f6feb;
    color: #ffffff;
}
"""
