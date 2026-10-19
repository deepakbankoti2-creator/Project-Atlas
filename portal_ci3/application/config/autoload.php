<?php
defined('BASEPATH') OR exit('No direct script access allowed');

$autoload['packages'] = array();
$autoload['libraries'] = array('session', 'atlas_client');
$autoload['drivers'] = array();
$autoload['helper'] = array('url', 'form', 'html', 'security');
$autoload['config'] = array('atlas');
$autoload['language'] = array();
$autoload['model'] = array('chat_model');
