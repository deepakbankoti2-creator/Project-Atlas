<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Config {
    public $config = array();
    public $is_loaded = array();

    public function __construct() {
        if (file_exists(APPPATH . 'config/config.php')) {
            require(APPPATH . 'config/config.php');
            if (isset($config) && is_array($config)) {
                $this->config = $config;
            }
        }
    }

    public function load($file = '', $use_sections = FALSE, $fail_gracefully = FALSE) {
        $file = ($file === '') ? 'config' : str_replace('.php', '', $file);
        $path = APPPATH . 'config/' . $file . '.php';
        if (file_exists($path)) {
            require($path);
            if (isset($config) && is_array($config)) {
                if ($use_sections === TRUE) {
                    $this->config[$file] = $config;
                } else {
                    $this->config = array_merge($this->config, $config);
                }
                $this->is_loaded[] = $path;
                return TRUE;
            }
        }
        return FALSE;
    }

    public function item($item, $index = '') {
        if ($index == '') {
            return isset($this->config[$item]) ? $this->config[$item] : NULL;
        }
        return isset($this->config[$index][$item]) ? $this->config[$index][$item] : NULL;
    }

    public function set_item($item, $value) {
        $this->config[$item] = $value;
    }
}
