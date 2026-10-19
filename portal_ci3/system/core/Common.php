<?php
defined('BASEPATH') OR exit('No direct script access allowed');

if (!function_exists('get_instance')) {
    function &get_instance() {
        return CI_Controller::get_instance();
    }
}

if (!function_exists('html_escape')) {
    function html_escape($var, $double_encode = TRUE) {
        if (empty($var)) return $var;
        if (is_array($var)) {
            foreach (array_keys($var) as $key) {
                $var[$key] = html_escape($var[$key], $double_encode);
            }
            return $var;
        }
        return htmlspecialchars($var, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8', $double_encode);
    }
}

if (!function_exists('log_message')) {
    function log_message($level, $message) {
        // Output to error_log or file
        error_log("[CI3 " . strtoupper($level) . "] " . $message);
    }
}

if (!function_exists('site_url')) {
    function site_url($uri = '') {
        $base = get_instance()->config->item('base_url');
        return rtrim($base, '/') . '/' . ltrim($uri, '/');
    }
}

if (!function_exists('base_url')) {
    function base_url($uri = '') {
        return site_url($uri);
    }
}

if (!function_exists('redirect')) {
    function redirect($uri = '', $method = 'auto', $code = NULL) {
        $url = site_url($uri);
        header("Location: {$url}", TRUE, $code ?: 302);
        exit;
    }
}
