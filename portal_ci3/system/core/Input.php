<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Input {
    public function method($upper = FALSE) {
        $method = isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : 'GET';
        return $upper ? strtoupper($method) : strtolower($method);
    }

    public function post($index = NULL, $xss_clean = NULL) {
        if ($index === NULL && !empty($_POST)) {
            return $_POST;
        }
        $val = isset($_POST[$index]) ? $_POST[$index] : NULL;
        if ($xss_clean === TRUE && $val !== NULL) {
            $security =& load_class('Security', 'core');
            return $security->xss_clean($val);
        }
        return $val;
    }

    public function get($index = NULL, $xss_clean = NULL) {
        if ($index === NULL && !empty($_GET)) {
            return $_GET;
        }
        $val = isset($_GET[$index]) ? $_GET[$index] : NULL;
        if ($xss_clean === TRUE && $val !== NULL) {
            $security =& load_class('Security', 'core');
            return $security->xss_clean($val);
        }
        return $val;
    }
}
