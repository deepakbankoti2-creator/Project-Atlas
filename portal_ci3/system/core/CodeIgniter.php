<?php
defined('BASEPATH') OR exit('No direct script access allowed');

require_once(BASEPATH . 'core/Common.php');

function &load_class($class, $directory = 'libraries', $param = NULL) {
    static $_classes = array();

    if (isset($_classes[$class])) {
        return $_classes[$class];
    }

    $name = FALSE;
    foreach (array(APPPATH, BASEPATH) as $path) {
        if (file_exists($path . $directory . '/' . $class . '.php')) {
            $name = 'CI_' . $class;
            if (class_exists($name, FALSE) === FALSE) {
                require_once($path . $directory . '/' . $class . '.php');
            }
            break;
        }
    }

    if ($name === FALSE) {
        exit('Unable to locate the specified class: ' . $class . '.php');
    }

    $_classes[$class] = isset($param) ? new $name($param) : new $name();
    return $_classes[$class];
}

// Load core classes
load_class('Config', 'core');
load_class('Security', 'core');
load_class('Input', 'core');
load_class('Output', 'core');

require_once(BASEPATH . 'core/Controller.php');
require_once(BASEPATH . 'core/Model.php');
load_class('Loader', 'core');

// Parse request URI
$uri_string = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '';
$uri_parts  = explode('?', $uri_string);
$path       = trim($uri_parts[0], '/');

// Strip subdirectories if any
$segments = array_filter(explode('/', $path));
if (!empty($segments) && reset($segments) === 'portal_ci3') {
    array_shift($segments);
}
if (!empty($segments) && reset($segments) === 'index.php') {
    array_shift($segments);
}

$controller_name = !empty($segments) ? ucfirst(array_shift($segments)) : 'Chat';
$method_name     = !empty($segments) ? array_shift($segments) : 'index';
$params          = $segments;

$controller_file = APPPATH . 'controllers/' . $controller_name . '.php';

if (!file_exists($controller_file)) {
    // Default to Chat controller
    $controller_name = 'Chat';
    $method_name     = 'index';
    $controller_file = APPPATH . 'controllers/Chat.php';
}

require_once($controller_file);

if (!class_exists($controller_name)) {
    header("HTTP/1.0 404 Not Found");
    echo "Controller {$controller_name} not found.";
    exit;
}

$CI = new $controller_name();

if (!method_exists($CI, $method_name)) {
    header("HTTP/1.0 404 Not Found");
    echo "Method {$method_name} not found in {$controller_name}.";
    exit;
}

call_user_func_array(array($CI, $method_name), $params);

$CI->output->_display();
