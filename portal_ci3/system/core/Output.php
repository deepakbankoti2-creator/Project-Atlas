<?php
defined('BASEPATH') OR exit('No direct script access allowed');

class CI_Output {
    protected $final_output = '';
    protected $status_code = 200;
    protected $headers = array();

    public function set_status_header($code = 200, $text = '') {
        $this->status_code = (int)$code;
        http_response_code($this->status_code);
        return $this;
    }

    public function set_content_type($mime_type, $charset = NULL) {
        $header = 'Content-Type: ' . $mime_type;
        if ($charset) {
            $header .= '; charset=' . $charset;
        }
        $this->headers[] = $header;
        header($header);
        return $this;
    }

    public function set_output($output) {
        $this->final_output = $output;
        return $this;
    }

    public function get_output() {
        return $this->final_output;
    }

    public function _display($output = '') {
        if ($output === '') {
            $output = $this->final_output;
        }
        echo $output;
    }
}
