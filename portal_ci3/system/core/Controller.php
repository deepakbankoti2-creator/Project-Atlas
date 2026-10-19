<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Controller {
    private static $instance;
    public $load;
    public $config;
    public $input;
    public $output;
    public $security;
    public $session;
    public $db;

    public function __construct() {
        self::$instance =& $this;

        $this->config   =& load_class('Config', 'core');
        $this->security =& load_class('Security', 'core');
        $this->input    =& load_class('Input', 'core');
        $this->output   =& load_class('Output', 'core');
        $this->load     =& load_class('Loader', 'core');

        // Autoload
        if (file_exists(APPPATH . 'config/autoload.php')) {
            require(APPPATH . 'config/autoload.php');
            if (isset($autoload['libraries'])) {
                foreach ($autoload['libraries'] as $lib) {
                    $this->load->library($lib);
                }
            }
            if (isset($autoload['helper'])) {
                $this->load->helper($autoload['helper']);
            }
            if (isset($autoload['config'])) {
                foreach ($autoload['config'] as $cfg) {
                    $this->config->load($cfg);
                }
            }
            if (isset($autoload['model'])) {
                foreach ($autoload['model'] as $m) {
                    $this->load->model($m);
                }
            }
        }
    }

    public static function &get_instance() {
        return self::$instance;
    }
}
