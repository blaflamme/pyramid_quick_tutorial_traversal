# -*- coding: utf-8 -*- 
<%inherit file="layout.mako"/>

<h1>Add a new task</h1>

<form action="${request.resource_url(request.context, 'new')}" method="post">
  <input type="text" maxlength="100" name="name">
  <input type="submit" name="add" value="ADD" class="button">
</form>
