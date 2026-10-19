<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Security {
    protected $_csrf_hash;
    protected $_csrf_expire = 7200;
    protected $_csrf_token_name = 'atlas_csrf_token';
    protected $_csrf_cookie_name = 'atlas_csrf_cookie';

    public function __construct() {
        if (isset($_COOKIE[$this->_csrf_cookie_name]) && preg_match('#^[0-9a-f]{32}$#iS', $_COOKIE[$this->_csrf_cookie_name]) === 1) {
            $this->_csrf_hash = $_COOKIE[$this->_csrf_cookie_name];
        } else {
            $this->_csrf_hash = md5(uniqid(mt_rand(), TRUE));
            setcookie($this->_csrf_cookie_name, $this->_csrf_hash, time() + $this->_csrf_expire, '/');
        }
    }

    public function get_csrf_token_name() {
        return $this->_csrf_token_name;
    }

    public function get_csrf_hash() {
        return $this->_csrf_hash;
    }

    public function xss_clean($str, $is_image = FALSE) {
        if (is_array($str)) {
            foreach ($str as $key => $val) {
                $str[$key] = $this->xss_clean($val, $is_image);
            }
            return $str;
        }
        return htmlspecialchars((string)$str, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }
}
