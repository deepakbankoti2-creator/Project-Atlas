<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Loader {
    protected $_ci_classes = array();
    protected $_ci_models = array();
    protected $_ci_helpers = array();

    public function view($view, $vars = array(), $return = FALSE) {
        $view_file = VIEWPATH . $view . '.php';
        if (!file_exists($view_file)) {
            show_error('Unable to load requested view: ' . $view);
        }

        if (is_array($vars)) {
            extract($vars);
        }

        ob_start();
        include($view_file);
        $buffer = ob_get_contents();
        ob_end_clean();

        if ($return === TRUE) {
            return $buffer;
        }

        $CI =& get_instance();
        $CI->output->set_output($buffer);
    }

    public function model($model, $name = '', $db_conn = FALSE) {
        if (empty($model)) return $this;
        $model = strtolower($model);
        $name = empty($name) ? $model : $name;

        if (in_array($name, $this->_ci_models, TRUE)) {
            return $this;
        }

        $model_class = ucfirst($model);
        $file_path = APPPATH . 'models/' . $model_class . '.php';
        if (!file_exists($file_path)) {
            $file_path = APPPATH . 'models/' . $model . '.php';
        }

        if (file_exists($file_path)) {
            require_once($file_path);
            $CI =& get_instance();
            $CI->$name = new $model_class();
            $this->_ci_models[] = $name;
        }

        return $this;
    }

    public function library($library, $params = NULL, $object_name = NULL) {
        if (empty($library)) return $this;
        if (is_array($library)) {
            foreach ($library as $lib) {
                $this->library($lib);
            }
            return $this;
        }

        $lib = strtolower($library);
        $class_name = ucfirst($lib);
        $obj_name = empty($object_name) ? $lib : $object_name;

        $file_path = APPPATH . 'libraries/' . $class_name . '.php';
        if (!file_exists($file_path)) {
            $file_path = BASEPATH . 'libraries/' . $class_name . '.php';
        }

        if (file_exists($file_path)) {
            require_once($file_path);
            $CI =& get_instance();
            $CI->$obj_name = new $class_name($params);
            $this->_ci_classes[$obj_name] = $class_name;
        } elseif ($lib === 'session') {
            // Built-in session wrapper
            if (session_status() === PHP_SESSION_NONE) {
                @session_start();
            }
            $CI =& get_instance();
            $CI->session = new class {
                public function userdata($key = NULL) {
                    if ($key === NULL) return $_SESSION;
                    return isset($_SESSION[$key]) ? $_SESSION[$key] : NULL;
                }
                public function set_userdata($key, $val = NULL) {
                    if (is_array($key)) {
                        foreach ($key as $k => $v) { $_SESSION[$k] = $v; }
                    } else {
                        $_SESSION[$key] = $val;
                    }
                }
                public function unset_userdata($key) {
                    unset($_SESSION[$key]);
                }
            };
        }

        return $this;
    }

    public function helper($helpers = array()) {
        if (is_string($helpers)) {
            $helpers = array($helpers);
        }
        foreach ($helpers as $helper) {
            $h = strtolower($helper) . '_helper.php';
            if (file_exists(APPPATH . 'helpers/' . $h)) {
                include_once(APPPATH . 'helpers/' . $h);
            } elseif (file_exists(BASEPATH . 'helpers/' . $h)) {
                include_once(BASEPATH . 'helpers/' . $h);
            }
        }
        return $this;
    }

    public function config($file = '', $use_sections = FALSE, $fail_gracefully = FALSE) {
        $CI =& get_instance();
        return $CI->config->load($file, $use_sections, $fail_gracefully);
    }

    public function database($params = '', $return = FALSE, $query_builder = NULL) {
        $CI =& get_instance();
        require_once(BASEPATH . 'database/DB.php');
        $db = CI_DB::get_instance();
        if ($return === TRUE) {
            return $db;
        }
        $CI->db = $db;
        return $this;
    }
}
