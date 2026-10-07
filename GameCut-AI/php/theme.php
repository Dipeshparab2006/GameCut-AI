<?php
/**
 * Theme System - Centralized design tokens and utilities
 * Ensures consistency across all pages
 */

// Design Tokens - Based on current implementation
define('COLOR_PRIMARY', '#7C3AED');
define('COLOR_PRIMARY_GLOW', 'rgba(124, 58, 237, 0.5)');
define('COLOR_SECONDARY', '#3B82F6');
define('COLOR_SECONDARY_GLOW', 'rgba(59, 130, 246, 0.5)');
define('COLOR_SUCCESS', '#10B981');
define('COLOR_WARNING', '#F59E0B');
define('COLOR_ERROR', '#EF4444');
define('COLOR_BACKGROUND', '#0F0F0F');
define('COLOR_CARD', '#1E1E1E');
define('COLOR_TEXT', '#FFFFFF');
define('COLOR_TEXT_MUTED', '#A1A1AA');
define('COLOR_BORDER', '#27272A');
define('COLOR_BORDER_LIGHT', '#3F3F46');

// Transition timing
define('TRANSITION_FAST', '150ms');
define('TRANSITION_NORMAL', '300ms');
define('TRANSITION_SLOW', '500ms');

// Shadow definitions
define('SHADOW_SM', '0 1px 2px rgba(0, 0, 0, 0.08)');
define('SHADOW_MD', '0 12px 32px rgba(0, 0, 0, 0.18)');
define('SHADOW_LG', '0 24px 60px rgba(0, 0, 0, 0.28)');

// Z-index values
define('Z_INDEX_HEADER', '100');
define('Z_INDEX_SIDEBAR', '200');
define('Z_INDEX_MODAL', '300');
define('Z_INDEX_TOAST', '1000');

// Breakpoints
define('BREAKPOINT_MOBILE', '768px');
define('BREAKPOINT_TABLET', '992px');
define('BREAKPOINT_DESKTOP', '1200px');

function themeGetColor($key) {
    $constants = [
        'primary' => COLOR_PRIMARY,
        'primary-glow' => COLOR_PRIMARY_GLOW,
        'secondary' => COLOR_SECONDARY,
        'secondary-glow' => COLOR_SECONDARY_GLOW,
        'success' => COLOR_SUCCESS,
        'warning' => COLOR_WARNING,
        'error' => COLOR_ERROR,
        'background' => COLOR_BACKGROUND,
        'card' => COLOR_CARD,
        'text' => COLOR_TEXT,
        'text-muted' => COLOR_TEXT_MUTED,
        'border' => COLOR_BORDER,
        'border-light' => COLOR_BORDER_LIGHT,
    ];
    return $constants[$key] ?? COLOR_CARD;
}

function themeCssVariable($key) {
    $color = themeGetColor($key);
    return "var(--$key: $color)";
}