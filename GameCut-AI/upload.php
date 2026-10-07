<?php
require_once 'php/bootstrap.php';
require_once 'php/config.php';
require_once 'php/session.php';

// Require authentication
requireAuth();

// Get current user data
$currentUser = getCurrentUser();
$flash = getFlashMessage();
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload - GameCut AI</title>
    <script src="js/theme-init.js"></script>
    <link rel="stylesheet" href="css/style.css">
    <link rel="stylesheet" href="css/dashboard.css">
    <link rel="stylesheet" href="css/upload.css">
    <link rel="stylesheet" href="css/responsive.css">
</head>
<body class="dashboard-body">
    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="sidebar-header">
            <a href="index.php" class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#paint0_linear_upload)" />
                    <path d="M2 17L12 22L22 17" stroke="url(#paint1_linear_upload)" stroke-width="2" stroke-linecap="round"/>
                    <path d="M2 12L12 17L22 12" stroke="url(#paint2_linear_upload)" stroke-width="2" stroke-linecap="round"/>
                    <defs>
                        <linearGradient id="paint0_linear_upload" x1="12" y1="2" x2="12" y2="12" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint1_linear_upload" x1="12" y1="17" x2="12" y2="22" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                        <linearGradient id="paint2_linear_upload" x1="12" y1="12" x2="12" y2="17" gradientUnits="userSpaceOnUse"><stop stop-color="#7C3AED" /><stop offset="1" stop-color="#3B82F6" /></linearGradient>
                    </defs>
                </svg>
                <span>GameCut <span class="text-gradient">AI</span></span>
            </a>
        </div>
        
        <nav class="sidebar-nav">
            <a href="dashboard.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                <span>Dashboard</span>
            </a>
            <a href="projects.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                <span>Projects</span>
            </a>
            <a href="upload.php" class="nav-item active">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <span>Upload</span>
            </a>
            <a href="upload.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg><span>AI Styles</span></a>
            <a href="preview.php" class="nav-item"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg><span>Results</span></a>
            <a href="settings.php" class="nav-item">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                <span>Settings</span>
            </a>
        </nav>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
        <header class="topbar">
            <div class="page-title">
                <h2>Upload Video</h2>
            </div>
            
            <div class="topbar-actions">
                <div class="profile-dropdown">
                    <div class="avatar">
                        <img src="https://ui-avatars.com/api/?name=<?php echo urlencode($currentUser['username'] ?? 'User'); ?>&background=7C3AED&color=fff" alt="User Avatar">
                    </div>
                </div>
            </div>
        </header>

        <div class="content-wrapper upload-wrapper">
            <div class="upload-container fade-in">
                <?php if ($flash): ?>
                    <div class="upload-alert upload-alert-<?php echo htmlspecialchars($flash['type']); ?>">
                        <?php echo htmlspecialchars($flash['message']); ?>
                    </div>
                <?php endif; ?>
                
                <form method="POST" action="php/upload_process.php" enctype="multipart/form-data" id="uploadForm">
                    <?php echo csrfField(); ?>
                    <!-- Upload Box -->
                    <div class="upload-box" id="uploadBox">
                    <div class="upload-icon-large">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                    </div>
                    <h3>Drag & Drop your gameplay here</h3>
                    <p class="text-muted">or <span class="browse-link" id="browseBtn">browse files</span></p>
                    
                    <input type="file" id="fileInput" name="gameplay_video" hidden accept="video/mp4,video/quicktime,video/x-matroska,video/x-msvideo,video/webm,.mp4,.mov,.mkv,.avi,.webm" required>
                    
                    <div class="upload-info">
                        <div class="info-item">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                            <span>MP4, MOV, MKV, AVI</span>
                        </div>
                        <div class="info-item">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                            <span>Max 2 hours</span>
                        </div>
                        <div class="info-item">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            <span>Max 1GB</span>
                        </div>
                    </div>
                    </div>

                    <!-- File Preview (Hidden by default) -->
                    <div class="file-preview-card hidden" id="filePreview">
                    <div class="preview-header">
                        <h4>Ready to process</h4>
                        <button type="button" class="icon-btn" id="removeFileBtn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                    </div>
                    
                    <div class="file-details">
                        <div class="file-icon">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>
                        </div>
                        <div class="file-meta">
                            <span class="file-name" id="fileName">valorant_clutch_raw.mp4</span>
                            <span class="file-size" id="fileSize">1.2 GB • 00:45:12</span>
                        </div>
                    </div>

                    <div class="upload-settings">
                        <div class="setting-group">
                            <label for="projectName">Project Name</label>
                            <input type="text" id="projectName" name="project_name" class="w-100" placeholder="Valorant clutch highlights">
                        </div>

                        <div class="setting-group">
                            <label for="gameSelect">Choose Game</label>
                            <select class="custom-select w-100" id="gameSelect" name="game">
                                <option>Free Fire</option>
                                <option>Valorant</option>
                                <option>PUBG / BGMI</option>
                                <option>Fortnite</option>
                                <option>CS2</option>
                                <option>Apex Legends</option>
                                <option>Other Game</option>
                            </select>
                        </div>

                        <div class="setting-group">
                            <label>Video Style</label>
                            <input type="hidden" id="styleInput" name="style" value="Esports">
                            <div class="platform-toggles option-grid" data-choice-group="style">
                                <button type="button" class="platform-btn active">Esports</button>
                                <button type="button" class="platform-btn">Funny</button>
                                <button type="button" class="platform-btn">Cinematic</button>
                                <button type="button" class="platform-btn">Fast Montage</button>
                                <button type="button" class="platform-btn">Fast Motion</button>
                                <button type="button" class="platform-btn">Kill Montage</button>
                                <button type="button" class="platform-btn">Clutch</button>
                                <button type="button" class="platform-btn">Slow Motion</button>
                            </div>
                        </div>

                        <div class="setting-group hidden" id="motionSpeedSettings" aria-live="polite">
                            <label id="motionSpeedLabel" for="playbackSpeed">Playback Speed</label>
                            <select class="custom-select w-100" id="playbackSpeed" name="playback_speed">
                                <option value="0.25">Very slow — 0.25×</option>
                                <option value="0.5" selected>Slow — 0.5×</option>
                                <option value="0.75">Gentle slow — 0.75×</option>
                                <option value="1.25">Slightly fast — 1.25×</option>
                                <option value="1.5">Fast — 1.5×</option>
                                <option value="2">Very fast — 2×</option>
                                <option value="3">Hyperlapse — 3×</option>
                                <option value="4">Hyperlapse — 4×</option>
                                <option value="8">Hyperlapse — 8×</option>
                            </select>
                            <p class="text-muted" id="motionSpeedHint">The selected speed applies to the entire uploaded video.</p>
                        </div>

                        <div class="setting-group" id="outputLengthSettings">
                            <label>Output Length</label>
                            <input type="hidden" id="lengthInput" name="output_length" value="30 sec">
                            <div class="platform-toggles option-grid" data-choice-group="length">
                                <button type="button" class="platform-btn active">30 sec</button>
                                <button type="button" class="platform-btn">45 sec</button>
                                <button type="button" class="platform-btn">60 sec</button>
                            </div>
                            <label for="targetDuration" class="text-muted" style="display:block;margin-top:0.75rem;">Custom output duration (seconds)</label>
                            <input type="number" id="targetDuration" name="target_duration" class="w-100" value="30" min="1" max="14400" step="1">
                            <p class="text-muted">Choose any duration up to 4 hours. The AI will use source timestamps across the whole video.</p>
                        </div>

                        <div class="setting-group">
                            <label>AI Add-ons</label>
                            <div class="ai-addons">
                                <label class="addon-toggle">
                                    <input type="checkbox" checked>
                                    <span>Subtitles</span>
                                </label>
                                <label class="addon-toggle">
                                    <input type="checkbox" checked>
                                    <span>Music</span>
                                </label>
                                <label class="addon-toggle">
                                    <input type="checkbox" checked>
                                    <span>Thumbnail</span>
                                </label>
                                <label class="addon-toggle">
                                    <input type="checkbox" checked>
                                    <span>Title & Hashtags</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    <button type="submit" class="btn btn-primary btn-lg w-100" id="startProcessingBtn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"></path><path d="M12 5l7 7-7 7"></path></svg>
                        Upload Gameplay
                    </button>
                    <div class="upload-progress hidden" id="uploadProgress">
                        <div class="upload-progress-header">
                            <span id="uploadProgressText">Uploading 0%</span>
                            <button type="button" class="btn btn-outline" id="cancelUploadBtn">Cancel</button>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="uploadProgressFill" style="width: 0%"></div>
                        </div>
                    </div>
                    </div>
                </form>

            </div>
        </div>
    </main>

    <script src="js/app.js"></script>
    <script src="js/upload.js"></script>
</body>
</html>
